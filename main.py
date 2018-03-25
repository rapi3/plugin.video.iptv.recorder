from xbmcswift2 import Plugin
import re
import requests
import xbmc,xbmcaddon,xbmcvfs,xbmcgui
import xbmcplugin
import base64
import random
import urllib
import sqlite3
import time
import threading
import json
import os,os.path
import stat
import subprocess
from datetime import datetime,timedelta
#TODO strptime bug fix
import uuid
import HTMLParser
import calendar

from struct import *
from collections import namedtuple


plugin = Plugin()
big_list_view = False



def addon_id():
    return xbmcaddon.Addon().getAddonInfo('id')


def log(v):
    xbmc.log(repr(v),xbmc.LOGERROR)


def get_icon_path(icon_name):
    if plugin.get_setting('user.icons') == "true":
        user_icon = "special://profile/addon_data/%s/icons/%s.png" % (addon_id(),icon_name)
        if xbmcvfs.exists(user_icon):
            return user_icon
    return "special://home/addons/%s/resources/img/%s.png" % (addon_id(),icon_name)


def remove_formatting(label):
    label = re.sub(r"\[/?[BI]\]",'',label)
    label = re.sub(r"\[/?COLOR.*?\]",'',label)
    return label


def escape( str ):
    str = str.replace("&", "&amp;")
    str = str.replace("<", "&lt;")
    str = str.replace(">", "&gt;")
    str = str.replace("\"", "&quot;")
    return str


def unescape( str ):
    str = str.replace("&lt;","<")
    str = str.replace("&gt;",">")
    str = str.replace("&quot;","\"")
    str = str.replace("&amp;","&")
    return str


def delete(path):
    dirs, files = xbmcvfs.listdir(path)
    for file in files:
        xbmcvfs.delete(path+file)
    for dir in dirs:
        delete(path + dir + '/')
    xbmcvfs.rmdir(path)


@plugin.route('/play/<channelid>')
def play(channelid):
    rpc = '{"jsonrpc":"2.0","method":"Player.Open","id":305,"params":{"item":{"channelid":%s}}}' % channelid
    r = requests.post('http://localhost:8080/jsonrpc',data=rpc)


@plugin.route('/play_channel/<channelname>')
def play_channel(channelname):
    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')))
    c = conn.cursor()
    channel = c.execute("SELECT * FROM streams WHERE name=?",(channelname,)).fetchone()
    if not channel:
        return
    name,tvg_name,tvg_id,tvg_logo,groups,url = channel

    xbmc.Player().play(url)


@plugin.route('/play_channel_external/<channelname>')
def play_channel_external(channelname):
    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')))
    c = conn.cursor()
    channel = c.execute("SELECT * FROM streams WHERE name=?",(channelname,)).fetchone()
    if not channel:
        return
    name,tvg_name,tvg_id,tvg_logo,groups,url = channel

    if url:
        cmd = [plugin.get_setting('external.player')]
        args = plugin.get_setting('external.player.args')
        if args:
            cmd.append(args)
        cmd.append(url)
        subprocess.Popen(cmd)


@plugin.route('/play_external/<path>')
def play_external(path):
    cmd = [plugin.get_setting('external.player')]
    args = plugin.get_setting('external.player.args')
    if args:
        cmd.append(args)
    cmd.append(xbmc.translatePath(path))
    subprocess.Popen(cmd)


def xml2local(xml):
    #TODO combine
    return utc2local(xml2utc(xml))


def utc2local(utc):
    timestamp = calendar.timegm(utc.timetuple())
    local = datetime.fromtimestamp(timestamp)
    return local.replace(microsecond=utc.microsecond)


def str2dt(string_date):
    format ='%Y-%m-%d %H:%M:%S'
    try:
        res = datetime.strptime(string_date, format)
    except TypeError:
        res = datetime(*(time.strptime(string_date, format)[0:6]))
    return utc2local(res)


def total_seconds(td):
    return (td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6) / 10**6


@plugin.route('/jobs')
def jobs():
    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')))
    c = conn.cursor()
    jobs = c.execute("SELECT * FROM jobs ORDER by channelname,start").fetchall()

    items = []
    for uuid, channelid, channelname, title, start, stop in jobs:
        etitle = HTMLParser.HTMLParser().unescape(title)
        echannelname = HTMLParser.HTMLParser().unescape(channelname)
        context_items = []
        context_items.append(("Delete Job" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_job,job=uuid))))
        context_items.append(("Delete All Jobs" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_all_jobs))))
        label = "%s - %s[CR][COLOR grey]%s - %s[/COLOR]" % (echannelname,etitle,xml2local(start),xml2local(stop))
        items.append({
            'label': label,
            'path': plugin.url_for(delete_job,job=uuid),
            'context_menu': context_items,
            'thumbnail':get_icon_path('recordings'),
        })
    return items


@plugin.route('/rules')
def rules():
    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')))
    c = conn.cursor()
    rules = c.execute("SELECT uid, channelid, channelname, title, start, stop, description, type FROM rules ORDER by channelname,title,start,stop").fetchall()

    items = []
    for uid, channelid, channelname, title, start, stop, description, type  in rules:
        if type == "PLOT":
            edescription = HTMLParser.HTMLParser().unescape(description)
        else:
            etitle = HTMLParser.HTMLParser().unescape(title)
        try: echannelname = HTMLParser.HTMLParser().unescape(channelname)
        except: pass

        context_items = []
        context_items.append(("Delete Rule" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_rule,uid=uid))))
        context_items.append(("Delete All Rules" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_all_rules))))
        #label = "%s - %s[CR][COLOR grey]%s - %s[/COLOR]" % (channelname,etitle,xml2local(start),xml2local(stop))
        label = "TODO"
        if type == "ALWAYS":
            label = "%s - %s" % (channelname,etitle)
        elif type == "DAILY":
            label =  "%s - %s[CR][COLOR grey]%s - %s[/COLOR]" % (echannelname,etitle,xml2local(start).time(),xml2local(stop).time())
        elif type == "SEARCH":
            label = "%s - %s" % (echannelname,etitle)
        elif type == "PLOT":
            label = "%s - (%s)" % (echannelname,edescription)
        items.append({
            'label': label,
            'path': plugin.url_for(delete_rule,uid=uid),
            'context_menu': context_items,
            'thumbnail':get_icon_path('recordings'),
        })
    return items


@plugin.route('/delete_all_rules')
def delete_all_rules(ask=True):
    if ask and not (xbmcgui.Dialog().yesno("IPTV Recorder","Delete All Rules?")):
        return

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')))
    conn.execute("DELETE FROM rules")
    conn.commit()
    conn.close()

    refresh()


@plugin.route('/delete_rule/<uid>')
def delete_rule(uid,kill=True,ask=True):
    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')))

    if ask and not (xbmcgui.Dialog().yesno("IPTV Recorder","Cancel Record?")):
        return

    conn.execute("DELETE FROM rules WHERE uid=?",(uid,))
    conn.commit()
    conn.close()

    refresh()


@plugin.route('/delete_all_jobs')
def delete_all_jobs(ask=True):
    if ask and not (xbmcgui.Dialog().yesno("IPTV Recorder","Delete All Jobs?")):
        return

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')))
    conn.execute("DELETE FROM jobs")
    conn.commit()
    conn.close()

    refresh()


@plugin.route('/delete_job/<job>')
def delete_job(job,kill=True,ask=True):
    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')))
    c = conn.cursor()
    job_details = c.execute("SELECT * FROM jobs WHERE uuid=?",(job,)).fetchone()
    if not job_details:
        return

    if ask and not (xbmcgui.Dialog().yesno("IPTV Recorder","Cancel Record?")):
        return

    if windows() and plugin.get_setting('task.scheduler') == 'true':
        cmd = ["schtasks","/delete","/f","/tn",job]
        subprocess.Popen(cmd,shell=True)
    else:
        xbmc.executebuiltin('CancelAlarm(%s,True)' % job)

    directory = "special://profile/addon_data/plugin.video.iptv.recorder/jobs/"
    xbmcvfs.mkdirs(directory)
    pyjob = directory + job + ".py"

    pid = xbmcvfs.File(pyjob+'.pid').read()
    if pid and kill:
        if windows():
            subprocess.Popen(["taskkill","/im",pid],shell=True)
        else:
            #TODO correct kill switch
            subprocess.Popen(["kill","-9",pid])

    xbmcvfs.delete(pyjob)
    xbmcvfs.delete(pyjob+'.pid')

    conn.execute("DELETE FROM jobs WHERE uuid=?",(job,))
    conn.commit()
    conn.close()

    refresh()


def windows():
    if os.name == 'nt':
        return True
    else:
        return False


def android_get_current_appid():
    with open("/proc/%d/cmdline" % os.getpid()) as fp:
        return fp.read().rstrip("\0")


def ffmpeg_location():
    ffmpeg_src = xbmc.translatePath(plugin.get_setting('ffmpeg'))
    if xbmc.getCondVisibility('system.platform.android'):
        ffmpeg_dst = '/data/data/%s/ffmpeg' % android_get_current_appid()
        if not xbmcvfs.exists(ffmpeg_dst) and ffmpeg_src != ffmpeg_dst:
            xbmcvfs.copy(ffmpeg_src,ffmpeg_dst)
        ffmpeg = ffmpeg_dst
    else:
        ffmpeg = ffmpeg_src

    if ffmpeg:
        try:
            st = os.stat(ffmpeg)
            if not (st.st_mode | stat.S_IXUSR):
                try:
                    os.chmod(ffmpeg, st.st_mode | stat.S_IXUSR)
                except:
                    pass
        except:
            pass
    if xbmcvfs.exists(ffmpeg):
        return ffmpeg
    else:
        xbmcgui.Dialog().notification("IPTV Recorder","ffmpeg exe not found!")


@plugin.route('/record_once/<channelid>/<channelname>/<title>/<start>/<stop>')
def record_once(channelid,channelname,title,start,stop):
    #TODO check for ffmpeg process already recording if job is re-added
    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')))
    c = conn.cursor()

    if channelid:
        channel = c.execute("SELECT * FROM streams WHERE tvg_id=?",(channelid,)).fetchone()
        if channel:
            name,tvg_name,tvg_id,tvg_logo,groups,url = channel

    if not url:
        xbmc.log("No url for %s" % channelname,xbmc.LOGERROR)
        return

    url_headers = url.split('|',1)
    url = url_headers[0]
    headers = {}
    if len(url_headers) == 2:
        sheaders = url_headers[1]
        aheaders = sheaders.split('&')
        if aheaders:
            for h in aheaders:
                k,v = h.split('=',1)
                headers[k] = v

    local_starttime = xml2local(start)
    local_endtime = xml2local(stop)
    etitle = HTMLParser.HTMLParser().unescape(title)
    label = "%s - %s[CR][COLOR grey]%s - %s[/COLOR]" % (channelname,etitle,local_starttime,local_endtime)

    job = c.execute("SELECT * FROM jobs WHERE channelid=? AND start=? AND stop=?",(channelid,start,stop)).fetchone()
    if job:
        return

    before = int(plugin.get_setting('minutes.before') or "0")
    after = int(plugin.get_setting('minutes.after') or "0")
    local_starttime = local_starttime - timedelta(minutes=before)
    local_endtime = local_endtime + timedelta(minutes=after)

    now = datetime.now()
    if (local_starttime < now) and (local_endtime > now):
        local_starttime = now
        immediate = True
    else:
        immediate = False

    length = local_endtime - local_starttime
    seconds = total_seconds(length)

    filename = urllib.quote_plus(label.encode("utf8"))+'.ts'
    path = os.path.join(xbmc.translatePath(plugin.get_setting('recordings')),filename)
    ffmpeg = ffmpeg_location()
    if not ffmpeg:
        return

    cmd = [ffmpeg]
    for h in headers:
        cmd.append("-headers")
        cmd.append("%s:%s" % (h,headers[h]))
    cmd.append("-i")
    cmd.append(url)
    probe_cmd = cmd
    cmd = probe_cmd + ["-y","-t",str(seconds),"-c","copy",path]

    directory = "special://profile/addon_data/plugin.video.iptv.recorder/jobs/"
    xbmcvfs.mkdirs(directory)
    job = str(uuid.uuid1())
    pyjob = directory + job + ".py"

    f = xbmcvfs.File(pyjob,'wb')
    f.write("import os,subprocess\n")
    f.write("probe_cmd = %s\n" % repr(probe_cmd))
    f.write("subprocess.call(probe_cmd,shell=%s)\n" % windows()) #TODO maybe optional
    f.write("cmd = %s\n" % repr(cmd))
    f.write("p = subprocess.Popen(cmd,shell=%s)\n" % windows())
    f.write("f = open(r'%s','w+')\n" % xbmc.translatePath(pyjob+'.pid'))
    f.write("f.write(repr(p.pid))\n")
    f.write("f.close()\n")
    #f.write("p.wait()\n")
    #f.write("os.unlink(%s)\n" % xbmc.translatePath(pyjob+'.pid'))
    f.close()

    if windows() and plugin.get_setting('task.scheduler') == 'true':
        if immediate:
            cmd = 'RunScript(%s)' % (pyjob)
            xbmc.executebuiltin(cmd)
        else:
            st = "%02d:%02d" % (local_starttime.hour,local_starttime.minute)
            sd = "%02d/%02d/%04d" % (local_starttime.day,local_starttime.month,local_starttime.year)
            cmd = ["schtasks","/create","/f","/tn",job,"/sc","once","/st",st,"/sd",sd,"/tr","%s %s" % (xbmc.translatePath(plugin.get_setting('python')),xbmc.translatePath(pyjob))]
            subprocess.Popen(cmd,shell=True)
    else:
        now = datetime.now()
        diff = local_starttime - now
        minutes = ((diff.days * 86400) + diff.seconds) / 60
        #minutes = 1
        if minutes < 1:
            if local_endtime > now:
                cmd = 'RunScript(%s)' % (pyjob)
                xbmc.executebuiltin(cmd)
            else:
                xbmcvfs.delete(pyjob)
                return
        else:
            cmd = 'AlarmClock(%s,RunScript(%s),%d,True)' % (job,pyjob,minutes)
            xbmc.executebuiltin(cmd)

    conn.execute("INSERT OR REPLACE INTO jobs(uuid,channelid,channelname,title,start,stop) VALUES(?,?,?,?,?,?)",
    [job,channelid,channelname,title,start,stop])
    conn.commit()
    conn.close()

    refresh()


def refresh():
    containerAddonName = xbmc.getInfoLabel('Container.PluginName')
    AddonName = xbmcaddon.Addon().getAddonInfo('id')
    if containerAddonName == AddonName:
        xbmc.executebuiltin('Container.Refresh')


@plugin.route('/record_daily/<channelid>/<channelname>/<title>/<start>/<stop>')
def record_daily(channelid,channelname,title,start,stop):
    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')))
    conn.execute("INSERT OR REPLACE INTO rules(channelid, channelname, title, start, stop, type) VALUES(?,?,?,?,?,?)",
    [channelid,channelname,title,start,stop,"DAILY"])
    conn.commit()
    conn.close()

    service()


@plugin.route('/record_always/<channelid>/<channelname>/<title>')
def record_always(channelid,channelname,title):
    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')))
    conn.execute("INSERT OR REPLACE INTO rules(channelid, channelname, title, type) VALUES(?,?,?,?)",
    [channelid,channelname,title,"ALWAYS"])
    conn.commit()
    conn.close()

    service()


@plugin.route('/record_always_search/<channelid>/<channelname>')
def record_always_search(channelid,channelname):
    title = xbmcgui.Dialog().input("IPTV Recorder: Title Search (% is wildcard)?")
    if not title:
        return

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')))
    conn.execute("INSERT OR REPLACE INTO rules(channelid, channelname, title,type) VALUES(?,?,?,?)",
    [channelid,channelname,title,"SEARCH"])
    conn.commit()
    conn.close()

    service()


@plugin.route('/record_always_search_plot/<channelid>/<channelname>')
def record_always_search_plot(channelid,channelname):
    title = xbmcgui.Dialog().input("IPTV Recorder: Plot Search (% is wildcard)?")
    if not title:
        return

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')))
    conn.execute("INSERT OR REPLACE INTO rules(channelid, channelname, description,type) VALUES(?,?,?,?)",
    [channelid,channelname,title,"PLOT"])
    conn.commit()
    conn.close()

    service()


@plugin.route('/broadcast/<channelid>/<channelname>/<title>/<start>/<stop>')
def broadcast(channelid,channelname,title,start,stop):
    label = HTMLParser.HTMLParser().unescape(title)
    echannelname = HTMLParser.HTMLParser().unescape(channelname)

    items = []

    items.append({
        'label': "Record Once - %s - %s[CR][COLOR grey]%s - %s[/COLOR]" % (echannelname,label,xml2local(start),xml2local(stop)),
        'path': plugin.url_for(record_once,channelid=channelid,channelname=channelname,title=title,start=start,stop=stop),
        'thumbnail':get_icon_path('recordings'),
    })

    items.append({
        'label': "Record Always - %s - %s" % (echannelname,label),
        'path': plugin.url_for(record_always,channelid=channelid,channelname=channelname,title=title),
        'thumbnail':get_icon_path('recordings'),
    })
    #TODO does this handle summer time?
    items.append({
        'label': "Record Daily - %s - %s[CR][COLOR grey]%s - %s[/COLOR]" % (echannelname,label,xml2local(start).time(),xml2local(stop).time()),
        'path': plugin.url_for(record_daily,channelid=channelid,channelname=channelname,title=title,start=start,stop=stop),
        'thumbnail':get_icon_path('recordings'),
    })

    return items


def day(timestamp):
    if timestamp:
        today = datetime.today()
        tomorrow = today + timedelta(days=1)
        yesterday = today - timedelta(days=1)
        if today.date() == timestamp.date():
            return 'Today'
        elif tomorrow.date() == timestamp.date():
            return 'Tomorrow'
        elif yesterday.date() == timestamp.date():
            return 'Yesterday'
        else:
            return timestamp.strftime("%A")


@plugin.route('/delete_search_title/<title>')
def delete_search_title(title):
    searches = plugin.get_storage('search_title')
    if title in searches:
        del searches[title]
    refresh()


@plugin.route('/search_title_dialog')
def search_title_dialog():
    searches = plugin.get_storage('search_title')

    items = []
    items.append({
        "label": "New",
        "path": plugin.url_for('search_title_input',title='title'),
        "thumbnail": get_icon_path('search'),
    })

    for search in searches:
        context_items = []
        context_items.append(("Delete Search" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_search_title,title=search))))
        items.append({
            "label": search,
            "path": plugin.url_for('search_title',title=search),
            "thumbnail": get_icon_path('search'),
            'context_menu': context_items,
            })
    return items


@plugin.route('/search_title_input/<title>')
def search_title_input(title):
    searches = plugin.get_storage('search_title')
    if title == "title":
        title = ""
    d = xbmcgui.Dialog()
    what = d.input("Search Title",title)
    if not what:
        return
    searches[what] = ''
    return search_title(what)


@plugin.route('/search_title/<title>')
def search_title(title):
    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')))
    c = conn.cursor()

    programmes = c.execute("SELECT * FROM programmes WHERE title LIKE ?",("%"+title+"%",)).fetchall()

    items = []
    for p in programmes:
        channelid , title , sub_title , start , stop , date , description , episode, categories = p
        channel = c.execute("SELECT * FROM streams WHERE tvg_id=?",(channelid,)).fetchone()
        if not channel:
            continue
        channelname,tvg_name,tvg_id,tvg_logo,groups,url = channel
        job = c.execute("SELECT * FROM jobs WHERE channelid=? AND start=? AND stop=?",(channelid,start,stop)).fetchone()
        if job:
            recording = "[COLOR red]RECORD[/COLOR]"
        else:
            recording = ""
        starttime = xml2local(start)
        endtime = xml2local(stop)
        if sub_title:
            stitle = "%s - %s" % (title,sub_title)
        else:
            stitle = title
        etitle = HTMLParser.HTMLParser().unescape(stitle)
        if description:
            description = HTMLParser.HTMLParser().unescape(description)
        label = "[COLOR grey]%02d:%02d %s - %s[/COLOR]  %s[CR]%s" % (starttime.hour,starttime.minute,day(starttime),HTMLParser.HTMLParser().unescape(channelname),recording,etitle)
        context_items = []
        if recording:
            context_items.append(("Cancel Record" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_job,job=job[0]))))
        else:
            context_items.append(("Record Once" , 'XBMC.RunPlugin(%s)' %
            (plugin.url_for(record_once,channelid=channelid,channelname=channelname.encode("utf8"),title=title.encode("utf8"),start=start,stop=stop))))
        context_items.append(("Play Channel" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(play_channel,channelname=channelname.encode("utf8")))))
        context_items.append(("Play Channel External" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(play_channel_external,channelname=channelname.encode("utf8")))))
        if url:
            path = plugin.url_for(broadcast,channelid=channelid,channelname=channelname.encode("utf8"),title=title.encode("utf8"),start=start,stop=stop)
        else:
            path = ""
        items.append({
            'label': label,
            'path': path,
            'thumbnail': tvg_logo,
            'context_menu': context_items,
            'info_type': 'Video',
            'info':{"title": etitle, "plot":description,"genre":categories}
        })
    return items

@plugin.route('/delete_search_plot/<plot>')
def delete_search_plot(plot):
    searches = plugin.get_storage('search_plot')
    if plot in searches:
        del searches[plot]
    refresh()


@plugin.route('/search_plot_dialog')
def search_plot_dialog():
    searches = plugin.get_storage('search_plot')

    items = []
    items.append({
        "label": "New",
        "path": plugin.url_for('search_plot_input',plot='plot'),
        "thumbnail": get_icon_path('search'),
    })

    for search in searches:
        context_items = []
        context_items.append(("Delete Search" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_search_plot,plot=search))))
        items.append({
            "label": search,
            "path": plugin.url_for('search_plot',plot=search),
            "thumbnail": get_icon_path('search'),
            'context_menu': context_items,
            })
    return items


@plugin.route('/search_plot_input/<plot>')
def search_plot_input(plot):
    searches = plugin.get_storage('search_plot')
    if plot == "plot":
        plot = ""
    d = xbmcgui.Dialog()
    what = d.input("Search Plot",plot)
    if not what:
        return
    searches[what] = ''
    return search_plot(what)


@plugin.route('/search_plot/<plot>')
def search_plot(plot):
    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')))
    c = conn.cursor()

    programmes = c.execute("SELECT * FROM programmes WHERE description LIKE ?",("%"+plot+"%",)).fetchall()

    items = []
    for p in programmes:
        channelid , title , sub_title , start , stop , date , description , episode, categories = p
        channel = c.execute("SELECT * FROM streams WHERE tvg_id=?",(channelid,)).fetchone()
        if not channel:
            continue
        channelname,tvg_name,tvg_id,tvg_logo,groups,url = channel
        job = c.execute("SELECT * FROM jobs WHERE channelid=? AND start=? AND stop=?",(channelid,start,stop)).fetchone()
        if job:
            recording = "[COLOR red]RECORD[/COLOR]"
        else:
            recording = ""
        starttime = xml2local(start)
        endtime = xml2local(stop)
        if sub_title:
            stitle = "%s - %s" % (title,sub_title)
        else:
            stitle = title
        etitle = HTMLParser.HTMLParser().unescape(stitle)
        if description:
            description = HTMLParser.HTMLParser().unescape(description)
        label = "[COLOR grey]%02d:%02d %s - %s[/COLOR]  %s[CR]%s" % (starttime.hour,starttime.minute,day(starttime),HTMLParser.HTMLParser().unescape(channelname),recording,etitle)
        context_items = []
        if recording:
            context_items.append(("Cancel Record" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_job,job=job[0]))))
        else:
            context_items.append(("Record Once" , 'XBMC.RunPlugin(%s)' %
            (plugin.url_for(record_once,channelid=channelid,channelname=channelname.encode("utf8"),title=title.encode("utf8"),start=start,stop=stop))))
        context_items.append(("Play Channel" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(play_channel,channelname=channelname.encode("utf8")))))
        context_items.append(("Play Channel External" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(play_channel_external,channelname=channelname.encode("utf8")))))
        if url:
            path = plugin.url_for(broadcast,channelid=channelid,channelname=channelname.encode("utf8"),title=title.encode("utf8"),start=start,stop=stop)
        else:
            path = ""
        items.append({
            'label': label,
            'path': path,
            'thumbnail': tvg_logo,
            'context_menu': context_items,
            'info_type': 'Video',
            'info':{"title": etitle, "plot":description,"genre":categories}
        })
    return items



@plugin.route('/channel/<channelname>/<channelid>')
def channel(channelname,channelid):
    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')))
    c = conn.cursor()
    channel = c.execute("SELECT * FROM streams WHERE tvg_id=?",(channelid,)).fetchone()
    if not channel:
        channel = c.execute("SELECT * FROM channels WHERE id=?",(channelid,)).fetchone()
        tvg_id, name, tvg_logo = channel
        url = ""
    else:
        name,tvg_name,tvg_id,tvg_logo,groups,url = channel
    programmes = c.execute("SELECT * FROM programmes WHERE channelid=?",(channelid,)).fetchall()
    #jobs = c.execute("SELECT * FROM jobs WHERE channelid=?",(channelid,)).fetchall()

    items = []
    for p in programmes:
        channel , title , sub_title , start , stop , date , description , episode, categories = p
        job = c.execute("SELECT * FROM jobs WHERE channelid=? AND start=? AND stop=?",(channelid,start,stop)).fetchone()
        if job:
            recording = "[COLOR red]RECORD[/COLOR]"
        else:
            recording = ""
        starttime = xml2local(start)
        endtime = xml2local(stop)
        if sub_title:
            stitle = "%s - %s" % (title,sub_title)
        else:
            stitle = title
        etitle = HTMLParser.HTMLParser().unescape(stitle)
        echannelname = HTMLParser.HTMLParser().unescape(channelname)
        if description:
            description = HTMLParser.HTMLParser().unescape(description)
        label = "[COLOR grey]%02d:%02d %s - %s[/COLOR] %s[CR]%s" % (starttime.hour,starttime.minute,day(starttime),echannelname,recording,etitle)
        context_items = []
        if recording:
            context_items.append(("Cancel Record" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_job,job=job[0]))))
        else:
            context_items.append(("Record Once" , 'XBMC.RunPlugin(%s)' %
            (plugin.url_for(record_once,channelid=channelid,channelname=channelname.encode("utf8"),title=title.encode("utf8"),start=start,stop=stop))))
        context_items.append(("Play Channel" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(play_channel,channelname=channelname.encode("utf8")))))
        context_items.append(("Play Channel External" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(play_channel_external,channelname=channelname.encode("utf8")))))
        if url:
            path = plugin.url_for(broadcast,channelid=channelid,channelname=channelname.encode("utf8"),title=title.encode("utf8"),start=start,stop=stop)
        else:
            path = plugin.url_for('channel',channelname=channelname,channelid=channelid)
        items.append({
            'label': label,
            'path': path,
            'thumbnail': tvg_logo,
            'context_menu': context_items,
            'info_type': 'Video',
            'info':{"title": etitle, "plot":description,"genre":categories}
        })
    return items


@plugin.route('/remove_favourite_channel/<channelname>')
def remove_favourite_channel(channelname):
    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')))
    conn.execute("DELETE FROM favourites WHERE channelname=?",(channelname,))
    conn.commit()
    conn.close()

    refresh()


@plugin.route('/add_favourite_channel/<channelname>/<channelid>/<thumbnail>')
def add_favourite_channel(channelname,channelid,thumbnail):
    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')))
    conn.execute("INSERT OR REPLACE INTO favourites(channelname,channelid,logo) VALUES(?,?,?)",
    [channelname,channelid,thumbnail])
    conn.commit()
    conn.close()

    refresh()


@plugin.route('/favourite_channels')
def favourite_channels():
    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')))
    c = conn.cursor()
    favourite_channels = c.execute("SELECT * FROM favourites").fetchall()

    items = []
    for channelname,channelid,thumbnail in favourite_channels:
        context_items = []
        context_items.append(("Add Title Search Rule" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(record_always_search,channelid=channelid,channelname=channelname.encode("utf8")))))
        context_items.append(("Add Plot Search Rule" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(record_always_search_plot,channelid=channelid,channelname=channelname.encode("utf8")))))
        context_items.append(("Play Channel" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(play_channel,channelname=channelname.encode("utf8")))))
        context_items.append(("Play Channel External" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(play_channel_external,channelname=channelname.encode("utf8")))))
        context_items.append(("Remove Favourite Channel" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(remove_favourite_channel,channelname=channelname))))
        items.append({
            'label': HTMLParser.HTMLParser().unescape(channelname),
            'path': plugin.url_for(channel,channelname=channelname,channelid=channelid),
            'context_menu': context_items,
            'thumbnail': thumbnail,
        })
    return items

@plugin.route('/epg')
def epg():
    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')))
    c = conn.cursor()

    streams = c.execute("SELECT * FROM streams ORDER BY name").fetchall()
    channels = c.execute("SELECT * FROM channels ORDER BY name").fetchall()
    favourites = c.execute("SELECT channelname FROM favourites").fetchall()
    favourites = [x[0] for x in favourites]

    items = []
    for c in channels:
        id, name, icon = c
        channelname = name
        channelid = id
        thumbnail = icon  or get_icon_path('tv')

        context_items = []
        context_items.append(("Add Title Search Rule" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(record_always_search,channelid=channelid,channelname=channelname.encode("utf8")))))
        context_items.append(("Add Plot Search Rule" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(record_always_search_plot,channelid=channelid,channelname=channelname.encode("utf8")))))
        context_items.append(("Play Channel" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(play_channel,channelname=channelname.encode("utf8")))))
        context_items.append(("Play Channel External" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(play_channel_external,channelname=channelname.encode("utf8")))))
        if channelname not in favourites:
            context_items.append(("Add Favourite Channel" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_favourite_channel,channelname=channelname,channelid=channelid,thumbnail=thumbnail))))
        else:
            context_items.append(("Remove Favourite Channel" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(remove_favourite_channel,channelname=channelname))))
        items.append({
            'label': HTMLParser.HTMLParser().unescape(name),
            'path': plugin.url_for(channel,channelname=name,channelid=channelid),
            'context_menu': context_items,
            'thumbnail': icon,
        })
    return items


@plugin.route('/group/<channelgroup>')
def group(channelgroup):
    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')))
    c = conn.cursor()

    if channelgroup == "All Channels":
        streams = c.execute("SELECT * FROM streams ORDER BY name").fetchall()
        channels = c.execute("SELECT * FROM streams ORDER BY name").fetchall()
    else:
        streams = c.execute("SELECT * FROM streams WHERE groups=? ORDER BY name",(channelgroup,)).fetchall()
    favourites = c.execute("SELECT channelname FROM favourites").fetchall()
    favourites = [x[0] for x in favourites]

    items = []
    for c in streams:
        name,tvg_name,tvg_id,tvg_logo,groups,url = c
        channelname = name
        channelid = tvg_id
        thumbnail = tvg_logo

        context_items = []
        context_items.append(("Add Title Search Rule" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(record_always_search,channelid=channelid,channelname=channelname.encode("utf8")))))
        context_items.append(("Add Plot Search Rule" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(record_always_search_plot,channelid=channelid,channelname=channelname.encode("utf8")))))
        context_items.append(("Play Channel" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(play_channel,channelname=channelname.encode("utf8")))))
        context_items.append(("Play Channel External" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(play_channel_external,channelname=channelname.encode("utf8")))))
        if channelname not in favourites:
            context_items.append(("Add Favourite Channel" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_favourite_channel,channelname=channelname,channelid=channelid,thumbnail=thumbnail))))
        else:
            context_items.append(("Remove Favourite Channel" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(remove_favourite_channel,channelname=channelname))))
        items.append({
            'label': HTMLParser.HTMLParser().unescape(name),
            'path': plugin.url_for(channel,channelname=name,channelid=channelid),
            'context_menu': context_items,
            'thumbnail': tvg_logo,
        })
    return items


@plugin.route('/groups')
def groups():
    items = []
    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')))
    c = conn.cursor()
    channelgroups = c.execute("SELECT DISTINCT groups FROM streams ORDER BY groups").fetchall()
    for channelgroup in [("All Channels",)] + channelgroups:
        channelgroup = channelgroup[0]
        if not channelgroup:
            continue
        items.append({
            'label': channelgroup,
            'path': plugin.url_for(group,channelgroup=channelgroup)

        })
    return items


@plugin.route('/service')
def service():
    threading.Thread(target=service_thread).start()

@plugin.route('/full_service')
def full_service():
    xmltv()
    service()

@plugin.route('/start')
def start():
    if not xbmcvfs.exists(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile'))):
        xmltv()
    service()

@plugin.route('/service_thread')
def service_thread():
    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')))
    c = conn.cursor()
    rules = c.execute("SELECT uid, channelid, channelname, title, start, stop, description, type FROM rules ORDER by channelname,title,start,stop").fetchall()

    for uid, jchannelid, jchannelname, jtitle, jstart, jstop, jdescription, type  in rules:

        if type == "ALWAYS":
            #TODO scrub [] from title
            programmes = c.execute("SELECT * FROM programmes WHERE channelid=? AND title=?",(jchannelid,jtitle)).fetchall()
            for p in programmes:
                channel , title , sub_title , start , stop , date , description , episode, categories = p
                record_once(jchannelid,jchannelname,title,start,stop)

        elif type == "DAILY":
            tjstart = xml2local(jstart).time()
            tjstop = xml2local(jstop).time()
            programmes = c.execute("SELECT * FROM programmes WHERE channelid=? AND title=?",(jchannelid,jtitle)).fetchall()
            for p in programmes:
                channel , title , sub_title , start , stop , date , description , episode, categories = p
                tstart = xml2local(start).time()
                tstop = xml2local(stop).time()
                if tjstart == tstart and tjstop == tstop:
                    record_once(jchannelid,jchannelname,title,start,stop)

        elif type == "SEARCH":
            programmes = c.execute("SELECT * FROM programmes WHERE channelid=? AND title LIKE ?",(jchannelid,jtitle)).fetchall()
            for p in programmes:
                channel , title , sub_title , start , stop , date , description , episode, categories = p
                record_once(jchannelid,jchannelname,title,start,stop)

        elif type == "PLOT":
            programmes = c.execute("SELECT * FROM programmes WHERE channelid=? AND description LIKE ?",(jchannelid,"%"+jdescription+"%")).fetchall()
            for p in programmes:
                channel , title , sub_title , start , stop , date , description , episode, categories = p
                record_once(jchannelid,jchannelname,title,start,stop)


@plugin.route('/delete_recording/<label>/<path>')
def delete_recording(label,path):
    if not (xbmcgui.Dialog().yesno("IPTV Recorder","[COLOR red]Delete Recording?[/COLOR]",label)):
        return
    xbmcvfs.delete(path)
    refresh()


@plugin.route('/delete_all_recordings')
def delete_all_recordings():
    if not (xbmcgui.Dialog().yesno("IPTV Recorder","[COLOR red]Delete All Recordings?[/COLOR]")):
        return
    dir = plugin.get_setting('recordings')
    dirs, files = xbmcvfs.listdir(dir)
    items = []
    for file in sorted(files):
        if file.endswith('.ts'):
            path = os.path.join(xbmc.translatePath(dir),file)
            xbmcvfs.delete(path)
    refresh()


@plugin.route('/recordings')
def recordings():
    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')))
    c = conn.cursor()
    streams = c.execute("SELECT name,tvg_logo FROM streams").fetchall()
    thumbnails = {x[0]:x[1] for x in streams}

    dir = plugin.get_setting('recordings')
    dirs, files = xbmcvfs.listdir(dir)
    items = []
    #TODO sort options
    for file in sorted(files):
        if file.endswith('.ts'):
            path = os.path.join(xbmc.translatePath(dir),file)
            label = urllib.unquote_plus(file)[0:-3]
            channelname = label.split(' - ',1)[0] #TODO meta info
            thumbnail = thumbnails.get(channelname)
            #TODO save some info from broadcast
            context_items = []
            context_items.append(("Delete Recording" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_recording,label=label,path=path))))
            context_items.append(("Delete All Recordings" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_all_recordings))))
            context_items.append(("External Player" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(play_external,path=path))))
            items.append({
                'label': label,
                'path': path,
                'thumbnail': thumbnail or get_icon_path('tv'),
                'is_playable': True,
                'context_menu': context_items,
                'info_type': 'Video',
                'info':{"title": label}
            })
    return items


def xml2utc(xml):
    match = re.search(r'([0-9]{4})([0-9]{2})([0-9]{2})([0-9]{2})([0-9]{2})([0-9]{2}) ([+-])([0-9]{2})([0-9]{2})',xml)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        day = int(match.group(3))
        hour = int(match.group(4))
        minute = int(match.group(5))
        second = int(match.group(6))
        sign = match.group(7)
        hours = int(match.group(8))
        minutes = int(match.group(9))
        dt = datetime(year,month,day,hour,minute,second)
        td = timedelta(hours=hours,minutes=minutes)
        if plugin.get_setting('xmltv.add.timezone') == "true":
            if sign == '+':
                dt = dt - td
            else:
                dt = dt + td
        return dt
    return ''


@plugin.route('/xmltv')
def xmltv():
    xbmcgui.Dialog().notification("IPTV Recorder","loading data",sound=False)

    profilePath = xbmc.translatePath(plugin.addon.getAddonInfo('profile'))
    xbmcvfs.mkdirs(profilePath)

    mode = plugin.get_setting('external.xmltv')
    if mode == "0":
        epgPathType = xbmcaddon.Addon('pvr.iptvsimple').getSetting('epgPathType')
        if epgPathType == "0":
            path = xbmcaddon.Addon('pvr.iptvsimple').getSetting('epgPath')
        else:
            path = xbmcaddon.Addon('pvr.iptvsimple').getSetting('epgUrl')
    elif mode == "1":
        path = plugin.get_setting('external.xmltv.file')
    else:
        path = plugin.get_setting('external.xmltv.url')
    #log((mode,epgPathType,path))
    tmp = os.path.join(profilePath,'xmltv.tmp')
    xml = os.path.join(profilePath,'xmltv.xml')
    xbmcvfs.copy(path,tmp)

    f = xbmcvfs.File(tmp,"rb")
    magic = f.read(3)
    f.close()
    if magic == "\x1f\x8b\x08":
        import gzip
        g = gzip.open(tmp)
        data = g.read()
        f = xbmcvfs.File(xml,"wb")
        f.write(data)
        f.close()
    else:
        xbmcvfs.copy(tmp,xml)

    databasePath = os.path.join(profilePath, 'xmltv.db')
    conn = sqlite3.connect(databasePath, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.execute('PRAGMA foreign_keys = ON')
    conn.row_factory = sqlite3.Row
    conn.execute('DROP TABLE IF EXISTS programmes')
    conn.execute('DROP TABLE IF EXISTS channels')
    conn.execute('DROP TABLE IF EXISTS streams')
    conn.execute('CREATE TABLE IF NOT EXISTS channels(id TEXT, name TEXT, icon TEXT, PRIMARY KEY (id))')
    conn.execute('CREATE TABLE IF NOT EXISTS programmes(channelid TEXT, title TEXT, sub_title TEXT, start TEXT, stop TEXT, date TEXT, description TEXT, episode TEXT, categories TEXT, PRIMARY KEY(channelid, start))')
    conn.execute('CREATE TABLE IF NOT EXISTS rules(uid INTEGER PRIMARY KEY ASC, channelid TEXT, channelname TEXT, title TEXT, sub_title TEXT, start TEXT, stop TEXT, date TEXT, description TEXT, episode TEXT, categories TEXT, type TEXT)')
    #TODO check primary key
    conn.execute('CREATE TABLE IF NOT EXISTS streams(name TEXT, tvg_name TEXT, tvg_id TEXT, tvg_logo TEXT, groups TEXT, url TEXT, PRIMARY KEY(name))')
    conn.execute('CREATE TABLE IF NOT EXISTS favourites(channelname TEXT, channelid TEXT, logo TEXT, PRIMARY KEY(channelname))')
    conn.execute('CREATE TABLE IF NOT EXISTS jobs(uuid TEXT, channelid TEXT, channelname TEXT, title TEXT, start TEXT, stop TEXT, PRIMARY KEY (uuid))')

    data = xbmcvfs.File(xml,'rb').read()

    match = re.findall('<channel(.*?)</channel>',data,flags=(re.I|re.DOTALL))
    if match:
        for m in match:
            id = re.search('id="(.*?)"',m)
            if id:
                id = id.group(1)
            name = re.search('<display-name.*?>(.*?)</display-name',m)
            if name:
                name = name.group(1)
            icon = re.search('<icon.*?src="(.*?)"',m)
            if icon:
                icon = icon.group(1)
            conn.execute("INSERT OR IGNORE INTO channels(id, name, icon) VALUES(?, ?, ?)", [id, name, icon])

    match = re.findall('<programme(.*?)</programme>',data,flags=(re.I|re.DOTALL))
    if match:
        for m in match:
            channel = re.search('channel="(.*?)"',m)
            if channel:
                channel = channel.group(1)
            start = re.search('start="(.*?)"',m)
            if start:
                start = start.group(1)
            stop = re.search('stop="(.*?)"',m)
            if stop:
                stop = stop.group(1)

            title = re.search('<title.*?>(.*?)</title',m)
            if title:
                title = title.group(1)
            sub_title = re.search('<sub-title.*?>(.*?)</sub-title',m)
            if sub_title:
                sub_title = sub_title.group(1)
            description = re.search('<desc.*?>(.*?)</desc',m)
            if description:
                description = description.group(1)
            date = re.search('<date.*?>(.*?)</date',m)
            if date:
                date = date.group(1)

            #TODO other systems
            episode = re.search('<episode-num system="xmltv_ns">(.*?)<',m)
            if episode:
                episode = episode.group(1)

            cats = re.findall('<category.*?>(.*?)</category>',m,flags=(re.I|re.DOTALL))
            if cats:
                categories = ','.join(cats)
            else:
                categories = ''

            conn.execute("INSERT OR IGNORE INTO programmes(channelid , title , sub_title , start , stop , date , description , episode, categories ) VALUES(?,?,?,?,?,?,?,?,?)",
            [channel , title , sub_title , start , stop , date , description , episode, categories])

    mode = plugin.get_setting('external.m3u')
    if mode == "0":
        m3uPathType = xbmcaddon.Addon('pvr.iptvsimple').getSetting('m3uPathType')
        if m3uPathType == "0":
            path = xbmcaddon.Addon('pvr.iptvsimple').getSetting('m3uPath')
        else:
            path = xbmcaddon.Addon('pvr.iptvsimple').getSetting('m3uUrl')
    elif mode == "1":
        path = plugin.get_setting('external.m3u.file')
    else:
        path = plugin.get_setting('external.m3u.url')
    m3uFile = 'special://profile/addon_data/plugin.video.iptv.recorder/channels.m3u'
    xbmcvfs.copy(path,m3uFile)
    f = xbmcvfs.File(m3uFile)
    data = f.read()

    channels = re.findall('#EXTINF:(.*?)\n(.*?)\n',data,flags=(re.I|re.DOTALL))
    for channel in channels:
        name = channel[0].rsplit(',',1)[-1]
        tvg_name = re.search('tvg-name="(.*?)"',channel[0])
        if tvg_name:
            tvg_name = tvg_name.group(1)
        tvg_id = re.search('tvg-id="(.*?)"',channel[0])
        if tvg_id:
            tvg_id = tvg_id.group(1)
        else:
            tvg_id = name
        tvg_logo = re.search('tvg-logo="(.*?)"',channel[0])
        if tvg_logo:
            tvg_logo = tvg_logo.group(1)

        url = channel[1]
        groups = re.search('group-title="(.*?)"',channel[0])
        if groups:
            groups = groups.group(1)

        conn.execute("INSERT OR IGNORE INTO streams(name,tvg_name,tvg_id,tvg_logo,groups,url ) VALUES(?,?,?,?,?,?)",
        [name.strip(),tvg_name,tvg_id,tvg_logo,groups,url.strip()])

    conn.commit()
    conn.close()

    xbmcgui.Dialog().notification("IPTV Recorder","finished loading data",sound=False)
    return


@plugin.route('/')
def index():
    items = []
    context_items = []

    items.append(
    {
        'label': "Favourite Channels",
        'path': plugin.url_for('favourite_channels'),
        'thumbnail':get_icon_path('favourites'),
        'context_menu': context_items,
    })

    items.append(
    {
        'label': "Channel Groups",
        'path': plugin.url_for('groups'),
        'thumbnail':get_icon_path('folder'),
        'context_menu': context_items,
    })

    items.append(
    {
        'label': "Recording Jobs",
        'path': plugin.url_for('jobs'),
        'thumbnail':get_icon_path('recordings'),
        'context_menu': context_items,
    })


    items.append(
    {
        'label': "Recording Rules",
        'path': plugin.url_for('rules'),
        'thumbnail':get_icon_path('recordings'),
        'context_menu': context_items,
    })

    items.append(
    {
        'label': "Recordings",
        'path': plugin.url_for('recordings'),
        'thumbnail':get_icon_path('recordings'),
        'context_menu': context_items,
    })

    items.append(
    {
        'label': "Recordings Folder",
        'path': plugin.get_setting('recordings'),
        'thumbnail':get_icon_path('recordings'),
        'context_menu': context_items,
    })

    items.append(
    {
        'label': "Full EPG",
        'path': plugin.url_for('epg'),
        'thumbnail':get_icon_path('favourites'),
        'context_menu': context_items,
    })

    items.append(
    {
        'label': "Search Title",
        'path': plugin.url_for('search_title_dialog'),
        'thumbnail':get_icon_path('search'),
        'context_menu': context_items,
    })

    items.append(
    {
        'label': "Search Plot",
        'path': plugin.url_for('search_plot_dialog'),
        'thumbnail':get_icon_path('search'),
        'context_menu': context_items,
    })

    if plugin.get_setting('debug') == "true":
        items.append(
        {
            'label': "Service",
            'path': plugin.url_for('service'),
            'thumbnail':get_icon_path('settings'),
            'context_menu': context_items,
        })

        items.append(
        {
            'label': "Start",
            'path': plugin.url_for('start'),
            'thumbnail':get_icon_path('settings'),
            'context_menu': context_items,
        })

        items.append(
        {
            'label': "xmltv",
            'path': plugin.url_for('xmltv'),
            'thumbnail':get_icon_path('settings'),
            'context_menu': context_items,
        })

    return items


if __name__ == '__main__':
    plugin.run()
