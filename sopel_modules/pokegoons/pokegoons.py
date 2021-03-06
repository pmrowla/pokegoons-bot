# -*- coding: utf-8 -*-
# Copyright (c) 2013 Peter Rowlands
"""
#pokegoons sopel module

Author: Peter "astroman" Rowlands <peter@pmrowla.com>
"""

from __future__ import unicode_literals, absolute_import, division

from sopel import web
from sopel.module import commands, example
from sopel.config import ConfigurationError

from HTMLParser import HTMLParser

from os import path

import json
import sqlite3 as lite
import re


def setup(bot):
    """Setup pokegoons module"""
    setup_fc(bot)


def setup_fc(bot):
    if not bot.db:
        raise ConfigurationError('Database not available')
    conn = bot.db.connect()
    c = conn.cursor()
    try:
        c.execute('SELECT * FROM fc_codes')
    except StandardError:
        c.execute('''
            CREATE TABLE IF NOT EXISTS fc_codes (
                nick TEXT,
                game TEXT,
                code TEXT,
                PRIMARY KEY (nick, game))
            ''')
        conn.commit()
    conn.close()


@commands('fc')
@example('.fc masuda')
def fc(bot, trigger):
    """Retreive your friend codes or codes for the specified nick"""
    if not trigger.match.group(2):
        nick = trigger.nick
    else:
        nick = trigger.match.group(2).strip()
    sub = '?'
    conn = bot.db.connect()
    c = conn.cursor()
    c.execute('SELECT * FROM fc_codes WHERE nick LIKE {0}'.format(sub),
              (nick,))
    rows = c.fetchall()
    if not rows:
        bot.say("Couldn't find any FCs for <%s>" % nick)
    else:
        msgs = []
        for (n, game, code) in rows:
            msgs.append('%s: %s' % (game, code))
        msg = "%s's friend codes: %s" % (nick, msgs[0])
        for m in msgs[1:]:
            if len(msg) >= 400:
                bot.reply(msg)
                msg = '(continued)'
            msg = '%s | %s' % (msg, m)
        bot.say(msg)
    conn.close()


@commands('setfc', 'addfc')
@example('.setfc 3DS = 1234-1234-1234')
def setfc(bot, trigger):
    """Add or update a friend code for the specified game"""
    usage = 'Usage: .setfc <game> = <code>'
    if not trigger.match.group(2):
        bot.reply(usage)
        return
    try:
        (game, code) = trigger.match.group(2).split('=', 1)
    except ValueError:
        bot.reply(usage)
        return
    game = game.strip()
    code = code.strip()
    sub = '?'
    conn = bot.db.connect()
    c = conn.cursor()
    c.execute('''
        SELECT * FROM fc_codes WHERE nick LIKE {0} AND game LIKE {0}
        '''.format(sub), (trigger.nick, game))
    row = c.fetchone()
    if not row:
        c.execute('''
            INSERT INTO fc_codes (nick, game, code) VALUES ({0}, {0}, {0})
            '''.format(sub), (trigger.nick, game, code))
    else:
        (nick, game, old_code) = row
        c.execute('''
            UPDATE fc_codes SET code = {0} WHERE nick = {0} AND game = {0}
            '''.format(sub), (code, trigger.nick, game))
    bot.reply('Set code for <%s> to <%s>' % (game, code))
    conn.commit()
    conn.close()


@commands('delfc', 'remfc')
@example('.delfc 3DS')
def delfc(bot, trigger):
    """Delete your friend code for the specified game"""
    if not trigger.match.group(2):
        return
    game = trigger.match.group(2).strip()
    sub = '?'
    conn = bot.db.connect()
    c = conn.cursor()
    c.execute(
        'SELECT * FROM fc_codes WHERE nick = {0} AND game = {0}'.format(sub),
        (trigger.nick, game))
    if c.fetchone():
        c.execute('''
            DELETE FROM fc_codes WHERE nick = {0} AND game = {0}
            '''.format(sub), (trigger.nick, game))
        bot.reply('Deleted code for %s' % (game))
        conn.commit()
    else:
        bot.reply('Could not find a matching code to delete')
    conn.close()


@commands('clearfc')
def clearfc(bot, trigger):
    """Delete ALL of your friend codes"""
    sub = '?'
    conn = bot.db.connect()
    c = conn.cursor()
    c.execute(
        'SELECT * FROM fc_codes WHERE nick = {0}'.format(sub),
        (trigger.nick,))
    if c.fetchone():
        c.execute('''
            DELETE FROM fc_codes WHERE nick = {0}
            '''.format(sub), (trigger.nick,))
        bot.reply('Deleted all of your friend codes')
        conn.commit()
    else:
        bot.reply('Could not find any matching codes to delete')
    conn.close()


@commands('table')
def table(bot, trigger):
    bot.say(u'(ノ ゜Д゜)ノ ︵ ┻━┻')


@commands('b', 'bulb', 'bulbapedia')
@example('.b charizard')
def bulbapedia(bot, trigger):
    """Search bulbapedia"""

    if trigger.group(2) is None:
        bot.reply("what do you want me to look up?")
        return

    query = trigger.group(2)

    if not query:
        bot.reply('what do you want me to look up?')
        return
    server = 'bulbapedia.bulbagarden.net'
    result = mw_search(server, query, 1)
    if not result:
        bot.reply("i can't find any results for that.")
        return
    (title, snippet) = result

    bot.say('"%s" - http://bulbapedia.bulbagarden.net/wiki/%s' % (
        strip_tags(snippet).strip(), title.replace(' ', '_')))


@commands('data')
@example('.data bulbasaur')
def data(bot, trigger):
    """Give information about selected pokemon"""

    if trigger.group(2):
        """Joke response for missingno"""
        if 'missingno' in trigger.group(2).lower():
            bot.say("PokedexError: 'dex' codec can't find pokemon 0xcc in"
                    " position 0: ordinal not in range(128) (Please stop"
                    " looking)")
        dbDir = path.join(path.dirname(__file__))
        con = lite.connect(path.join(dbDir, '../../pokedex.db'))
        with con:
            # Handle the input to take into account different orderings of the
            # word mega and use of hyphens
            reg = re.compile(
                r"(?:[\ -](mega)|(mega)[\ -])([a-z]*)(?:[\ -](X|Y))?",
                re.IGNORECASE)
            retrieved = trigger.group(2).strip()
            name = reg.search(retrieved)
            poke = reg.findall(retrieved)
            if poke:
                name = name.group(3)
                poke = filter(None, poke[0])
                poke = [poke for poke in poke if poke != name]
                retrieved = reg.sub(r"\3", retrieved)
                for match in poke:
                    retrieved = retrieved + '-' + match

            """Search the database and make the output somewhat pretty"""
            cur = con.cursor()
            cur.execute(
                """
                SELECT dexNo, species, type1, type2, genderRatio, hp, atk,
                pdef, spa, sdef, spd, ability1, ability2, hiddenAbility, egg1,
                egg2 FROM Pokedex WHERE UPPER(species) = {0}
                """.format('?'),
                (retrieved.upper(),))
            rows = cur.fetchall()
            for row in rows:
                dexInfo = 'No. ' + str(row[0]) + ' ' + row[1] + ' [' + row[2]
                if row[3]:
                    dexInfo = dexInfo + ', ' + row[3] + ']'
                else:
                    dexInfo = dexInfo + ']'

                if row[4]:
                    dexInfo = dexInfo + ' M/F '
                    if row[4] == 0.5:
                        dexInfo = dexInfo + '1:1'
                    elif row[4] == 0:
                        dexInfo = dexInfo + '0:1'
                    elif row[4] == 1:
                        dexInfo = dexInfo + '1:0'
                    elif row[4] == 0.875:
                        dexInfo = dexInfo + '7:1'

                dexInfo = dexInfo + ', Hp ' + str(row[5]) + ' | Atk ' + \
                    str(row[6]) + ' | Def ' + str(row[7]) + ' | SpA ' + \
                    str(row[8]) + ' | SpD ' + str(row[9]) + ' | Spe ' + \
                    str(row[10])+','

                if row[12] == '' and row[13] == '':
                    dexInfo = dexInfo + ' Ability: ' + row[11]
                elif row[12] == '':
                    dexInfo = dexInfo + ' Abilities: ' + row[11] + ' <' + \
                        row[13] + '>'
                elif row[13] == '':
                    dexInfo = dexInfo + ' Abilities: ' + row[11] + '/' + \
                        row[12]
                else:
                    dexInfo = dexInfo + ' Abilities: ' + row[11] + '/' + \
                        row[12] + ' <' + row[13] + '>'

                if row[15] == '':
                    dexInfo = dexInfo + ' {Egg: ' + row[14] + row[15] + '}'
                else:
                    dexInfo = dexInfo + ' {Egg: ' + row[14] + ', ' + \
                        row[15] + '}'
                bot.say(dexInfo)


def mw_search(server, query, num):
    """
    Searches the specified MediaWiki server for the given query, and returns
    the specified number of results.
    """
    search_url = ('http://%s/w/api.php?format=json&action=query'
                  '&list=search&srlimit=%d&srprop=timestamp|snippet'
                  '&srwhat=text'
                  '&srsearch=') % (server, num)
    search_url += query
    query = json.loads(web.get(search_url))
    if 'query' in query:
        try:
            query = query['query']['search'][0]
            return (query['title'], query['snippet'])
        except IndexError:
            return None
    else:
        return None


class MLStripper(HTMLParser):

    def __init__(self):
        self.reset()
        self.fed = []

    def handle_data(self, d):
        self.fed.append(d)

    def get_data(self):
        return ''.join(self.fed)


def strip_tags(html):
    s = MLStripper()
    s.feed(html)
    return s.get_data()
