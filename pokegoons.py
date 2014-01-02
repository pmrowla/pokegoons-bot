# -*- coding: utf-8 -*-
# Copyright (c) 2013 Peter Rowlands
"""
#pokegoons willie module

Author: Peter "astroman" Rowlands <peter@pmrowla.com>
"""

import requests

from bs4 import BeautifulSoup

from gdata.gauth import OAuth2Token
from gdata.spreadsheets.client import SpreadsheetsClient, ListQuery
from gdata.service import RequestError

from willie.module import commands, rule
from willie.config import ConfigurationError


# Google data API info, you most likely don't want to edit this
GDATA_CLIENT_ID = '259362750735-m2q2cg50r2n9jjvj7gvgh2v4hkd9m9o2' \
    '.apps.googleusercontent.com'
GDATA_CLIENT_SECRET = 'pWtIHW5ymP7c5EE4NmZvKGWd'
GDATA_SCOPE = ' '.join([
    'https://spreadsheets.google.com/feeds/',
    'https://docs.google.com/feeds/'
])
GDATA_USER_AGENT = 'willie/pokegoons'

# pokegoons spreadsheet key
GOON_KEY = '0AiGAq6LFMm6RdHlEU09XLVRXMnJXUFhGZC1uWjFnZlE'
# pokegoons shiny worksheet id
GOON_ID = 'od8'
# #shinyvalue spreadsheet
SV_KEY = '0Ak2hDRJIzJHbdFItaVJidTRTZTJxZnY1dThxNzRxbHc'


def check_shiny(bot, trigger, shiny_num):
    q = ListQuery(sq='shinynumber==%d' % shiny_num)
    try:
        feed = bot.ss_client.get_list_feed(GOON_KEY, GOON_ID, query=q)
    except RequestError, e:
        bot.say('Error: %s' % e)
    if len(feed.entry) == 0:
        bot.say('[%4d] No matches' % (shiny_num))
    for entry in feed.entry:
        username = entry.get_value('username')
        fc = entry.get_value('friendcode')
        bot.say('[%4d] Goon: %s - FC: %s' % (shiny_num, username, fc))


@rule(''.join([
    ur'(?i)(?P<pokemon>\w+) \((?P<gender>F|M)\) - (?P<nature>\w+), ',
    ur'(?P<ability>[\w ]+), (?P<ivs>(\d{1,2}\\){5}\d{1,2}) ',
    ur'\[(?P<shiny_num>\d{1,4})\]']))
def instacheck_egg(bot, trigger):
    """Handle regex for an instacheck egg line

    Example:
        Sneasel (F) - Jolly, Pickpocket, 31\31\31\31\31\15 [2514]
    """
    shiny_num = int(trigger.match.group('shiny_num'))
    check_shiny(bot, trigger, shiny_num)


def parse_showdown_log(bot, trigger, log):
    """Parse the a pokemon showdown log"""
    match_data = {}
    for line in log.splitlines():
        line = line.lstrip('|').strip()
        parts = line.split('|')
        if parts[0] == 'player' and len(parts) > 2:
            # there are occasionally garbage player entries for when a player
            # leaves, so we verify length
            match_data[parts[1]] = parts[2]
        elif parts[0] == 'gametype':
            match_data['gametype'] = parts[1]
        elif parts[0] == 'tier':
            match_data['tier'] = parts[1]
        elif parts[0] == 'win':
            match_data['win'] = parts[1]
    if match_data['win'] == match_data['p1']:
        match_data['p1_result'] = '(W)'
        match_data['p2_result'] = '(L)'
    elif match_data['win'] == match_data['p2']:
        match_data['p1_result'] = '(L)'
        match_data['p2_result'] = '(W)'
    msg = 'Pokemon showdown: %(tier)s %(gametype)s - ' \
        '%(p1)s %(p1_result)s vs %(p2)s %(p2_result)s' % match_data
    bot.reply(msg)


def parse_showdown_match(bot, trigger, html):
    """Parse the HTML for a pokemon showdown match"""
    soup = BeautifulSoup(html)
    for script in soup.find_all('script'):
        if script.has_attr('class'):
            return parse_showdown_log(bot, trigger, script.string)


@rule(''.join([
    ur'(?i).*http://replay\.pokemonshowdown\.com/(?P<match_id>[\w-]+)']))
def showdown_match(bot, trigger):
    """Handle regex for a pokemon showdown match link"""
    match_id = trigger.match.group('match_id')
    try:
        r = requests.get('http://replay.pokemonshowdown.com/%s' % match_id)
        r.raise_for_status()
        parse_showdown_match(bot, trigger, r.text)
    except requests.exceptions.HTTPError:
        pass


@commands('shiny')
def shiny(bot, trigger):
    """Query the pokegoons spreadsheet for a shiny match

    Usage: .shiny <number> [<number>...]
    """
    for num in trigger.match.group(2).split():
        try:
            shiny_num = int(num)
            check_shiny(bot, trigger, shiny_num)
        except ValueError:
            pass


def configure(config):
    """Configure pokegoons module

    Options:
        gdata_client_id: gdata API OAuth client ID
        gdata_client_secret: gdata API OAuth client secret
    """
    config.add_section('pokegoons')
    token = OAuth2Token(GDATA_CLIENT_ID, GDATA_CLIENT_SECRET,
                        GDATA_SCOPE, GDATA_USER_AGENT)
    url = token.generate_authorize_url()
    code = raw_input('Visit %s in a browser and then paste the '
                     'authorization code here: ' % (url))
    try:
        token.get_access_token(code)
    except:
        raise ConfigurationError('Could not obtain Google OAuth token')
    config.parser.set('pokegoons', 'access_token', token.access_token)
    config.parser.set('pokegoons', 'refresh_token', token.refresh_token)
    config.save()


def setup(bot):
    """Setup pokegoons module"""
    if not bot.config.has_option('pokegoons', 'access_token'):
        raise ConfigurationError('You must reconfigure the pokegoons module '
                                 'to obtain a Google OAuth token')
    if not bot.config.has_option('pokegoons', 'refresh_token'):
        raise ConfigurationError('You must reconfigure the pokegoons module '
                                 'to obtain a Google OAuth token')
    access_token = bot.config.parser.get('pokegoons', 'access_token')
    refresh_token = bot.config.parser.get('pokegoons', 'refresh_token')
    token = OAuth2Token(GDATA_CLIENT_ID, GDATA_CLIENT_SECRET, GDATA_SCOPE,
                        GDATA_USER_AGENT, access_token=access_token,
                        refresh_token=refresh_token)
    bot.ss_client = SpreadsheetsClient()
    token.authorize(bot.ss_client)
