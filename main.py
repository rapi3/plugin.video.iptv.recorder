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
    #log(r)
    #log(r.content)

@plugin.route('/play_name/<channelname>')
def play_name(channelname):
    channel_urls = plugin.get_storage("channel_urls")
    url = channel_urls.get(channelname)
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

def utc2local (utc):
    epoch = time.mktime(utc.timetuple())
    offset = datetime.fromtimestamp (epoch) - datetime.utcfromtimestamp (epoch)
    return utc + offset

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
    jobs = plugin.get_storage("jobs")
    jjobs = {x:json.loads(jobs[x]) for x in jobs}
    #log(jjobs)
    items = []
    #TODO sort options
    for j in sorted(jjobs, key=lambda x: (jjobs[x][2]),reverse=True):
        #log((j,jobs[j]))
        channelname,title,starttime,endtime = jjobs[j] #json.loads(jobs[j])
        context_items = []
        context_items.append(("Delete Job" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_job,job=j))))
        context_items.append(("Delete All Jobs" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_all_jobs))))
        items.append({
            'label': "%s - %s[CR][COLOR grey]%s %s - %s[/COLOR]" % (channelname,title,day(str2dt(starttime)),starttime,endtime),
            'path': plugin.url_for(delete_job,job=j),
            'context_menu': context_items,
            'thumbnail':get_icon_path('recordings'),
        })
    return items

@plugin.route('/rules')
def rules():
    items = []

    jobs = plugin.get_storage("channel_always_jobs")
    jjobs = {x:json.loads(jobs[x]) for x in jobs}
    #log(jjobs)
    #TODO sort options
    for j in sorted(jjobs, key=lambda x: (jjobs[x][1]),reverse=True):
        #log((j,jobs[j]))
        channelid,channelname,title = jjobs[j] #json.loads(jobs[j])
        context_items = []
        context_items.append(("Delete Job" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_channel_always_job,job=j))))
        items.append({
            'label': "%s - %s" % (channelname,title),
            'path': plugin.url_for(delete_channel_always_job,job=j),
            'thumbnail':get_icon_path('recordings'),
            'context_menu': context_items,
        })

    jobs = plugin.get_storage("channel_always_search_jobs")
    jjobs = {x:json.loads(jobs[x]) for x in jobs}
    #log(jjobs)
    #TODO sort options
    for j in sorted(jjobs, key=lambda x: (jjobs[x][1]),reverse=True):
        #log((j,jobs[j]))
        channelid,channelname,title = jjobs[j] #json.loads(jobs[j])
        context_items = []
        context_items.append(("Delete Job" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_channel_always_search_job,job=j))))
        items.append({
            'label': "%s - %s" % (channelname,title),
            'path': plugin.url_for(delete_channel_always_search_job,job=j),
            'thumbnail':get_icon_path('recordings'),
            'context_menu': context_items,
        })

    jobs = plugin.get_storage("channel_always_search_plot_jobs")
    jjobs = {x:json.loads(jobs[x]) for x in jobs}
    #log(jjobs)
    #TODO sort options
    for j in sorted(jjobs, key=lambda x: (jjobs[x][1]),reverse=True):
        #log((j,jobs[j]))
        channelid,channelname,title = jjobs[j] #json.loads(jobs[j])
        context_items = []
        context_items.append(("Delete Job" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_channel_always_search_plot_job,job=j))))
        items.append({
            'label': "%s - %s" % (channelname,title),
            'path': plugin.url_for(delete_channel_always_search_plot_job,job=j),
            'thumbnail':get_icon_path('recordings'),
            'context_menu': context_items,
        })

    jobs = plugin.get_storage("channel_daily_jobs")
    jjobs = {x:json.loads(jobs[x]) for x in jobs}
    #log(jjobs)
    #TODO sort options
    for j in sorted(jjobs, key=lambda x: (jjobs[x][1]),reverse=True):
        #log((j,jobs[j]))
        channelid,channelname,title,starttime,endtime = jjobs[j] #json.loads(jobs[j])
        context_items = []
        context_items.append(("Delete Job" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_channel_daily_job,job=j))))
        items.append({
            'label': "%s - %s[CR][COLOR grey]%s - %s[/COLOR]" % (channelname,title,str2dt(starttime).time(),str2dt(endtime).time()),
            'path': plugin.url_for(delete_channel_daily_job,job=j),
            'thumbnail':get_icon_path('recordings'),
            'context_menu': context_items,
        })

    return items

@plugin.route('/delete_channel_always_search_job/<job>')
def delete_channel_always_search_job(job):
    if not (xbmcgui.Dialog().yesno("IPTV Recorder","Cancel Recording Rule?")):
        return
    jobs = plugin.get_storage("channel_always_search_jobs")
    del jobs[job]
    refresh()

@plugin.route('/delete_channel_always_search_plot_job/<job>')
def delete_channel_always_search_plot_job(job):
    if not (xbmcgui.Dialog().yesno("IPTV Recorder","Cancel Recording Rule?")):
        return
    jobs = plugin.get_storage("channel_always_search_plot_jobs")
    del jobs[job]
    refresh()

@plugin.route('/delete_channel_always_job/<job>')
def delete_channel_always_job(job):
    if not (xbmcgui.Dialog().yesno("IPTV Recorder","Cancel Recording Rule?")):
        return
    jobs = plugin.get_storage("channel_always_jobs")
    del jobs[job]
    refresh()

@plugin.route('/delete_channel_daily_job/<job>')
def delete_channel_daily_job(job):
    if not (xbmcgui.Dialog().yesno("IPTV Recorder","Cancel Recording Rule?")):
        return
    jobs = plugin.get_storage("channel_daily_jobs")
    del jobs[job]
    refresh()

@plugin.route('/delete_all_jobs')
def delete_all_jobs(ask=True):
    if ask and not (xbmcgui.Dialog().yesno("IPTV Recorder","Delete All Jobs?")):
        return
    jobs = plugin.get_storage("jobs")
    jobs.clear()
    refresh()

@plugin.route('/delete_job/<job>')
def delete_job(job,kill=True,ask=True):
    #log(("DELETE JOB",job))
    #TODO stop ffmpeg task

    if ask and not (xbmcgui.Dialog().yesno("IPTV Recorder","Cancel Record?")):
        return
    jobs = plugin.get_storage("jobs")
    if job not in jobs:
        return

    if windows() and plugin.get_setting('task.scheduler') == 'true':
        cmd = ["schtasks","/delete","/f","/tn",job]
        #log(cmd)
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
            subprocess.Popen(["kill","-9",pid])

    xbmcvfs.delete(pyjob)
    xbmcvfs.delete(pyjob+'.pid')
    del jobs[job]

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
            if not (st.st_mode | stat.S_IEXEC):
                try:
                    os.chmod(ffmpeg, st.st_mode | stat.S_IEXEC)
                except:
                    pass
        except:
            pass
    if xbmcvfs.exists(ffmpeg):
        return ffmpeg
    else:
        xbmcgui.Dialog().notification("IPTV Recorder","ffmpeg exe not found!")



@plugin.route('/record_once/<channelname>/<channelid>/<title>/<start>/<stop>')
def record_once(channelname,channelid,title,start,stop):
    #TODO check for ffmpeg process already recording if job is re-added

    '''
    channel_urls = plugin.get_storage("channel_urls")
    if not len(channel_urls.keys()):
        m3u()
    if not len(channel_urls.keys()):
        xbmcgui.Dialog().notification("IPTV Recorder","No m3u Channels found!")

    url = channel_urls.get(channelname)
    '''
    if channelid:
        conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')))
        c = conn.cursor()
        channel = c.execute("SELECT * FROM streams WHERE tvg_id=?",(channelid,)).fetchone()
        conn.commit()
        conn.close()
        name,tvg_name,tvg_id,tvg_logo,groups,url = channel
        log(channel)

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

    local_starttime = xml2local(start) #str2dt(starttime)
    local_endtime = xml2local(stop) #str2dt(endtime)
    etitle = HTMLParser.HTMLParser().unescape(title)
    label = "%s - %s[CR][COLOR grey]%s - %s[/COLOR]" % (channelname,etitle,local_starttime,local_endtime)

    '''
    jobs = plugin.get_storage("jobs")
    job_description = json.dumps((channelname,title,start,stop))
    if job_description in jobs.values():
        return
    '''
    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')))
    c = conn.cursor()
    job = c.execute("SELECT * FROM jobs WHERE channelid=? AND start=? AND stop=?",(channelid,start,stop)).fetchone()
    conn.commit()
    conn.close()
    if job:
        log("FOUND")
        return

    before = int(plugin.get_setting('minutes.before') or "0")
    after = int(plugin.get_setting('minutes.after') or "0")
    #log((before,after))
    local_starttime = local_starttime - timedelta(minutes=before)
    local_endtime = local_endtime + timedelta(minutes=after)

    now = datetime.now()
    if (local_starttime < now) and (local_endtime > now):
        local_starttime = now
        immediate = True
    else:
        immediate = False
    #log((immediate,now,local_starttime,local_endtime))

    length = local_endtime - local_starttime
    seconds = total_seconds(length)
    #log((local_starttime,local_endtime,length))

    filename = urllib.quote_plus(label.encode("utf8"))+'.ts'
    path = os.path.join(xbmc.translatePath(plugin.get_setting('recordings')),filename)
    ffmpeg = ffmpeg_location()
    if not ffmpeg:
        return
    #ffmpeg = "notepad"
    cmd = [ffmpeg]
    for h in headers:
        cmd.append("-headers")
        cmd.append("%s:%s" % (h,headers[h]))
    cmd.append("-i")
    cmd.append(url)
    probe_cmd = cmd
    cmd = probe_cmd + ["-y","-t",str(seconds),"-c","copy",path]
    #probe_cmd = [ffmpeg,"-i",url]
    #log(cmd)

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
            #log(cmd)
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
                #pass
                xbmcvfs.delete(pyjob)
                return #TODO
        else:
            cmd = 'AlarmClock(%s,RunScript(%s),%d,True)' % (job,pyjob,minutes)
            #log(cmd)
            xbmc.executebuiltin(cmd)

    #jobs[job] = job_description

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')))
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

@plugin.route('/record_daily/<channelid>/<channelname>/<title>/<starttime>/<endtime>')
def record_daily(channelid,channelname,title,starttime,endtime):
    jobs = plugin.get_storage("channel_daily_jobs")
    job_description = json.dumps((channelid,channelname,title,starttime,endtime))
    job = str(uuid.uuid1())
    jobs[job] = job_description
    service()

@plugin.route('/record_always/<channelid>/<channelname>/<title>')
def record_always(channelid,channelname,title):
    jobs = plugin.get_storage("channel_always_jobs")
    job_description = json.dumps((channelid,channelname,title))
    job = str(uuid.uuid1())
    jobs[job] = job_description
    service()

@plugin.route('/record_always_search/<channelid>/<channelname>')
def record_always_search(channelid,channelname):
    title = xbmcgui.Dialog().input("IPTV Recorder: Title Search regex?")
    if not title:
        return
    jobs = plugin.get_storage("channel_always_search_jobs")
    job_description = json.dumps((channelid,channelname,title))
    job = str(uuid.uuid1())
    jobs[job] = job_description
    service()


@plugin.route('/record_always_search_plot/<channelid>/<channelname>')
def record_always_search_plot(channelid,channelname):
    title = xbmcgui.Dialog().input("IPTV Recorder: Plot Search regex?")
    if not title:
        return
    jobs = plugin.get_storage("channel_always_search_plot_jobs")
    job_description = json.dumps((channelid,channelname,title))
    job = str(uuid.uuid1())
    jobs[job] = job_description
    service()

@plugin.route('/broadcast/<channelid>/<channelname>/<title>/<start>/<stop>')
def broadcast(channelid,channelname,title,start,stop):
    label = HTMLParser.HTMLParser().unescape(title)
    #log((channelname,title,starttime,endtime))
    items = []
    #TODO format dates
    items.append({
        'label': "Record Once - %s - %s[CR][COLOR grey]%s - %s[/COLOR]" % (channelname,label,xml2local(start),xml2local(stop)),
        'path': plugin.url_for(record_once,channelid=channelid,channelname=channelname,title=title,start=start,stop=stop),
        'thumbnail':get_icon_path('recordings'),
    })
    return items
    items.append({
        'label': "Record Always - %s - %s" % (channelname,label),
        'path': plugin.url_for(record_always,channelid=channelid,channelname=channelname,title=title),
        'thumbnail':get_icon_path('recordings'),
    })
    items.append({
        'label': "Record Daily - %s - %s[CR][COLOR grey]%s - %s[/COLOR]" % (channelname,label,str2dt(starttime).time(),str2dt(endtime).time()),
        'path': plugin.url_for(record_daily,channelid=channelid,channelname=channelname,title=title,starttime=starttime,endtime=endtime),
        'thumbnail':get_icon_path('recordings'),
    })
    if False:
        items.append({
            'label': "Watch Once - %s - %s[CR][COLOR grey]%s - %s[/COLOR]" % (channelname,label,starttime,endtime),
            'path': plugin.url_for(record_once,channelname=channelname,title=title,starttime=starttime,endtime=endtime)
        })
        items.append({
            'label': "Watch Daily - %s - %s[CR][COLOR grey]%s - %s[/COLOR]" % (channelname,label,starttime,endtime),
            'path': plugin.url_for(record_daily,channelname=channelname,title=title,starttime=starttime,endtime=endtime)
        })
        items.append({
            'label': "Watch Always - %s - %s" % (channelname,label),
            'path': plugin.url_for(record_always,channelname=channelname,title=title)
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


@plugin.route('/channel/<channelname>/<channelid>')
def channel(channelname,channelid):
    '''
    channel_thumbnails = plugin.get_storage("channel_thumbnails")
    thumbnail = channel_thumbnails.get(channelname)
    jobs = plugin.get_storage("jobs")
    job_descriptions = {jobs[x]:x for x in jobs}
    rpc = '{"jsonrpc":"2.0","method":"PVR.GetBroadcasts","id":1,"params":{"channelid":%s,"properties":["title","plot","plotoutline","starttime","endtime","runtime","progress","progresspercentage","genre","episodename","episodenum","episodepart","firstaired","hastimer","isactive","parentalrating","wasactive","thumbnail","rating"]}}' % channelid
    r = requests.get('http://localhost:8080/jsonrpc?request='+urllib.quote_plus(rpc))
    content = r.content
    j = json.loads(content)
    #log(j)
    result = j.get('result')
    if not result:
        return
    broadcasts = result.get('broadcasts')
    if not broadcasts:
        return
    '''
    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')))
    c = conn.cursor()
    channel = c.execute("SELECT * FROM streams WHERE tvg_id=?",(channelid,)).fetchone()
    name,tvg_name,tvg_id,tvg_logo,groups,url = channel
    log(channel)
    programmes = c.execute("SELECT * FROM programmes WHERE channelid=?",(channelid,)).fetchall()
    #log(channels)
    items = []
    for p in programmes:
        log(p)
        channel , title , sub_title , start , stop , date , description , episode, categories = p
        starttime = xml2local(start)
        endtime = xml2local(stop)
        context_items = []
        if sub_title:
            title = "%s - %s" % (title,sub_title)
        etitle = HTMLParser.HTMLParser().unescape(title)
        if description:
            description = HTMLParser.HTMLParser().unescape(description)
        label = "[COLOR grey]%s %02d:%02d[/COLOR] [CR]%s" % (day(starttime),starttime.hour,starttime.minute,etitle)
        items.append({
            'label': label,
            'path': plugin.url_for(broadcast,channelid=channelid,channelname=channelname.encode("utf8"),title=title.encode("utf8"),start=start,stop=stop),
            'thumbnail': tvg_logo,
            'context_menu': context_items,
            'info_type': 'Video',
            'info':{"title": etitle, "plot":description,"genre":categories}
        })
    return items
    items = []
    for b in broadcasts:
        #log(b)
        starttime = b.get('starttime')
        endtime = b.get('endtime')
        title = b.get('title')
        plot = b.get('plot')
        genre = ','.join(b.get('genre'))
        job_description = json.dumps((channelname,title,starttime,endtime))
        broadcastid=str(b.get('broadcastid'))
        #log(starttime)
        start = str2dt(starttime)
        #log(start)
        recording = ""
        if job_description in job_descriptions:
            recording = "[COLOR red]RECORD[/COLOR]"
        label = "[COLOR grey]%s %02d:%02d[/COLOR] %s %s" % (day(start),start.hour,start.minute,b.get('label'),recording)
        context_items = []
        if recording:
            context_items.append(("Cancel Record" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_job,job=job_descriptions[job_description]))))
        else:
            context_items.append(("Record Once" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(record_once,channelname=channelname.encode("utf8"),title=title.encode("utf8"),starttime=starttime,endtime=endtime))))
        context_items.append(("PVR Player" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(play,channelid=channelid))))
        context_items.append(("External Player" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(play_name,channelname=channelname.encode("utf8")))))
        items.append({
            'label': label,
            'path': plugin.url_for(broadcast,channelid=channelid,channelname=channelname.encode("utf8"),title=title.encode("utf8"),starttime=starttime,endtime=endtime),
            'thumbnail': thumbnail,
            'context_menu': context_items,
            'info_type': 'Video',
            'info':{"title": channelname, "plot":plot,"genre":genre}
        })
    return items

@plugin.route('/remove_favourite_channel/<channelname>')
def remove_favourite_channel(channelname):
    favourite_channels = plugin.get_storage("favourite_channels")
    del favourite_channels[channelname]
    refresh()

@plugin.route('/add_favourite_channel/<channelname>/<channelid>/<thumbnail>')
def add_favourite_channel(channelname,channelid,thumbnail):
    favourite_channels = plugin.get_storage("favourite_channels")
    favourite_channels[channelname] = json.dumps((channelid,thumbnail))
    refresh()

@plugin.route('/favourite_channels')
def favourite_channels():
    favourite_channels = plugin.get_storage("favourite_channels")
    items = []
    for channelname in favourite_channels:
        channelid,thumbnail = json.loads(favourite_channels.get(channelname))
        context_items = []
        context_items.append(("Add Title Search Rule" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(record_always_search,channelid=channelid,channelname=channelname.encode("utf8")))))
        context_items.append(("Add Plot Search Rule" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(record_always_search_plot,channelid=channelid,channelname=channelname.encode("utf8")))))
        context_items.append(("PVR Player" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(play,channelid=channelid))))
        context_items.append(("External Player" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(play_name,channelname=channelname.encode("utf8")))))
        if channelname not in favourite_channels:
            context_items.append(("Add Favourite Channel" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_favourite_channel,channelname=channelname,channelid=channelid,thumbnail=thumbnail))))
        else:
            context_items.append(("Remove Favourite Channel" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(remove_favourite_channel,channelname=channelname))))
        items.append({
            'label': channelname,
            'path': plugin.url_for(channel,channelname=channelname,channelid=channelid),
            'context_menu': context_items,
            'thumbnail': thumbnail,
        })
    return items

@plugin.route('/group/<channelgroup>')
def group(channelgroup):
    '''
    channel_urls = plugin.get_storage("channel_urls")
    favourite_channels = plugin.get_storage("favourite_channels")
    channel_thumbnails = plugin.get_storage("channel_thumbnails")
    rpc = '{"jsonrpc":"2.0","method":"PVR.GetChannels","id":1,"params":{"channelgroupid":%s,"properties":["thumbnail","channeltype","hidden","locked","channel","lastplayed","broadcastnow","broadcastnext"]}}' % channelgroupid
    r = requests.get('http://localhost:8080/jsonrpc?request='+urllib.quote_plus(rpc))
    content = r.content
    j = json.loads(content)
    #log(j)
    channels = j.get('result').get('channels')
    '''
    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')))
    c = conn.cursor()
    '''
    if channelgroup == "All Channels":
        channels = c.execute("SELECT * FROM streams ORDER BY name").fetchall()
    else:
        channels = c.execute("SELECT * FROM streams ORDER BY name WHERE groups=?",(channelgroup,)).fetchall()
    '''
    if channelgroup == "All Channels":
        streams = c.execute("SELECT * FROM streams ORDER BY name").fetchall()
        channels = c.execute("SELECT * FROM streams ORDER BY name").fetchall()
    else:
        streams = c.execute("SELECT * FROM streams ORDER BY name WHERE groups=?",(channelgroup,)).fetchall()
    #log(channels)
    items = []
    for c in streams:
        name,tvg_name,tvg_id,tvg_logo,groups,url = c
        #id,name,logo = c
        #log(c)
        #label = c.get('label')
        #channelname = c.get('channel')
        #channelid = str(c.get('channelid'))
        #thumbnail = c.get('thumbnail')
        #channel_thumbnails[channelname] = thumbnail
        #log((name,cid))
        context_items = []
        #context_items.append(("Add Title Search Rule" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(record_always_search,channelid=channelid,channelname=channelname.encode("utf8")))))
        #context_items.append(("Add Plot Search Rule" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(record_always_search_plot,channelid=channelid,channelname=channelname.encode("utf8")))))
        #context_items.append(("PVR Player" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(play,channelid=channelid))))
        #context_items.append(("External Player" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(play_name,channelname=channelname.encode("utf8")))))
        #if label not in favourite_channels:
        #    context_items.append(("Add Favourite Channel" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_favourite_channel,channelname=channelname,channelid=channelid,thumbnail=thumbnail))))
        #else:
        #    context_items.append(("Remove Favourite Channel" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(remove_favourite_channel,channelname=channelname))))
        items.append({
            'label': name,
            'path': plugin.url_for(channel,channelname=name,channelid=tvg_id),
            'context_menu': context_items,
            'thumbnail': tvg_logo,
        })
    return items

@plugin.route('/groups')
def groups():

    '''
    rpc = '{"jsonrpc":"2.0","method":"PVR.GetChannelGroups","id":1,"params":{"channeltype":"tv"}}'
    r = requests.get('http://localhost:8080/jsonrpc?request='+urllib.quote_plus(rpc))
    content = r.content
    j = json.loads(content)
    #log(j)
    channelgroups = j.get('result').get('channelgroups')
    '''
    items = []
    #for channelgroup in channelgroups:
    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')))
    c = conn.cursor()
    channelgroups = c.execute("SELECT DISTINCT groups FROM streams ORDER BY groups").fetchall()
    for channelgroup in [("All Channels",)] + channelgroups:
        channelgroup = channelgroup[0]
        log(channelgroup)
        items.append({
            'label': channelgroup,
            'path': plugin.url_for(group,channelgroup=channelgroup)

        })
    return items

@plugin.route('/m3u')
def m3u():
    m3uUrl = xbmcaddon.Addon('pvr.iptvsimple').getSetting('m3uUrl')
    #log(m3uUrl)
    if plugin.get_setting('external.m3u') == "1":
        m3uUrl = plugin.get_setting('external.m3u.file')
    elif plugin.get_setting('external.m3u') == "2":
        m3uUrl = plugin.get_setting('external.m3u.url')
    m3uFile = 'special://profile/addon_data/plugin.video.iptv.recorder/channels.m3u'
    xbmcvfs.copy(m3uUrl,m3uFile)
    f = xbmcvfs.File(m3uFile)
    data = f.read()
    #log(data)
    channel_urls = plugin.get_storage("channel_urls")
    channel_urls.clear()
    channels = re.findall('#EXTINF:(.*?)\n(.*?)\n',data,flags=(re.I|re.DOTALL))
    for channel in channels:
        #log(channel)
        match = re.search('tvg-name="(.*?)"',channel[0])
        if match:
            name = match.group(1)
        else:
            name = channel[0].rsplit(',',1)[-1]
        url = channel[1]
        #log((name,url))
        channel_urls[name] = url
    #channel_urls.sync()

@plugin.route('/service_start')
def service_start():
    threading.Thread(target=service).start()

@plugin.route('/service')
def service():
    m3u()
    cache = {}
    jobs = plugin.get_storage("channel_always_jobs")
    for job in jobs:
        channelid,channelname,job_title = json.loads(jobs[job])
        rpc = '{"jsonrpc":"2.0","method":"PVR.GetBroadcasts","id":1,"params":{"channelid":%s,"properties":["title","plot","plotoutline","starttime","endtime","runtime","progress","progresspercentage","genre","episodename","episodenum","episodepart","firstaired","hastimer","isactive","parentalrating","wasactive","thumbnail","rating"]}}' % channelid
        r = requests.get('http://localhost:8080/jsonrpc?request='+urllib.quote_plus(rpc))
        content = r.content
        j = json.loads(content)
        #log(j)
        broadcasts = j.get('result').get('broadcasts')
        if not broadcasts:
            continue
        cache[channelid] = broadcasts
        for b in broadcasts:
            #log(b)
            starttime = b.get('starttime')
            endtime = b.get('endtime')
            title = b.get('title')
            if job_title == title:
                record_once(channelname,title,starttime,endtime)

    jobs = plugin.get_storage("channel_always_search_jobs")
    for job in jobs:
        channelid,channelname,job_title = json.loads(jobs[job])
        if channelid in cache:
            broadcasts = cache[channelid]
        else:
            rpc = '{"jsonrpc":"2.0","method":"PVR.GetBroadcasts","id":1,"params":{"channelid":%s,"properties":["title","plot","plotoutline","starttime","endtime","runtime","progress","progresspercentage","genre","episodename","episodenum","episodepart","firstaired","hastimer","isactive","parentalrating","wasactive","thumbnail","rating"]}}' % channelid
            r = requests.get('http://localhost:8080/jsonrpc?request='+urllib.quote_plus(rpc))
            content = r.content
            j = json.loads(content)
            #log(j)
            broadcasts = j.get('result').get('broadcasts')
            if not broadcasts:
                continue
            cache[channelid] = broadcasts
        for b in broadcasts:
            #log(b)
            starttime = b.get('starttime')
            endtime = b.get('endtime')
            title = b.get('title')
            #log((title,job_title,re.search(title,job_title,flags=re.I)))
            if re.search(job_title,title,flags=re.I):
                record_once(channelname,title,starttime,endtime)

    jobs = plugin.get_storage("channel_always_search_plot_jobs")
    for job in jobs:
        channelid,channelname,job_plot = json.loads(jobs[job])
        if channelid in cache:
            broadcasts = cache[channelid]
        else:
            rpc = '{"jsonrpc":"2.0","method":"PVR.GetBroadcasts","id":1,"params":{"channelid":%s,"properties":["title","plot","plotoutline","starttime","endtime","runtime","progress","progresspercentage","genre","episodename","episodenum","episodepart","firstaired","hastimer","isactive","parentalrating","wasactive","thumbnail","rating"]}}' % channelid
            r = requests.get('http://localhost:8080/jsonrpc?request='+urllib.quote_plus(rpc))
            content = r.content
            j = json.loads(content)
            #log(j)
            broadcasts = j.get('result').get('broadcasts')
            if not broadcasts:
                continue
            cache[channelid] = broadcasts
        for b in broadcasts:
            #log(b)
            starttime = b.get('starttime')
            endtime = b.get('endtime')
            title = b.get('title')
            plot = b.get('plot')
            #log((job_plot,plot,re.search(job_plot,plot,flags=re.I)))
            if re.search(job_plot,plot,flags=re.I):
                record_once(channelname,title,starttime,endtime)

    jobs = plugin.get_storage("channel_daily_jobs")
    for job in jobs:
        channelid,channelname,job_title,job_starttime,job_endtime = json.loads(jobs[job])
        if channelid in cache:
            broadcasts = cache[channelid]
        else:
            rpc = '{"jsonrpc":"2.0","method":"PVR.GetBroadcasts","id":1,"params":{"channelid":%s,"properties":["title","plot","plotoutline","starttime","endtime","runtime","progress","progresspercentage","genre","episodename","episodenum","episodepart","firstaired","hastimer","isactive","parentalrating","wasactive","thumbnail","rating"]}}' % channelid
            r = requests.get('http://localhost:8080/jsonrpc?request='+urllib.quote_plus(rpc))
            content = r.content
            j = json.loads(content)
            #log(j)
            broadcasts = j.get('result').get('broadcasts')
            if not broadcasts:
                continue
            cache[channelid] = broadcasts
        for b in broadcasts:
            #log(b)
            starttime = b.get('starttime')
            endtime = b.get('endtime')
            title = b.get('title')
            st = str2dt(starttime).time()
            jst = str2dt(job_starttime).time()
            et = str2dt(endtime).time()
            jet = str2dt(job_endtime).time()
            #log((st,jst,et,jet))
            #TODO add margin of time and fuzzy title match
            title = re.sub('\[.*?\]','',title).strip()
            job_title = re.sub('\[.*?\]','',job_title).strip()
            #log((title,job_title,st,jst,et,jet))
            if title == job_title and st == jst and et == jet:
                #log("RECORD ONCE")
                record_once(channelname,title,starttime,endtime)

@plugin.route('/start')
def start():
    m3u()
    #log("START")
    #TODO delete old timers
    jobs = plugin.get_storage("jobs")
    jobs_copy = dict(jobs)
    for job in jobs_copy:
        channelname,title,starttime,endtime = json.loads(jobs_copy[job])
        #delete_job(job,kill=False) #TODO more logic
        st = str2dt(starttime)
        et = str2dt(endtime)
        now = datetime.now()
        if st > now and not (windows() and plugin.get_setting('task.scheduler') == "true"):
            #log(("XXX",now,st,et,channelname,title,starttime,endtime))
            delete_job(job,ask=False)
            record_once(channelname,title,starttime,endtime)
        if et < now:
            delete_job(job,ask=False)


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
    channel_thumbnails = plugin.get_storage("channel_thumbnails")

    dir = plugin.get_setting('recordings')
    dirs, files = xbmcvfs.listdir(dir)
    items = []
    #TODO sort options
    for file in sorted(files):
        if file.endswith('.ts'):
            path = os.path.join(xbmc.translatePath(dir),file)
            label = urllib.unquote_plus(file)[0:-3]
            channelname = label.split(' - ',1)[0] #TODO meta info
            thumbnail = channel_thumbnails.get(channelname)
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
        if sign == '+':
            dt = dt - td
        else:
            dt = dt + td
        return dt
    return ''



class FileWrapper(object):
    def __init__(self, filename):
        self.vfsfile = xbmcvfs.File(filename)
        self.size = self.vfsfile.size()
        self.bytesRead = 0

    def close(self):
        self.vfsfile.close()

    def read(self, byteCount):
        self.bytesRead += byteCount
        return self.vfsfile.read(byteCount)

    def tell(self):
        return self.bytesRead


@plugin.route('/xmltv')
def xmltv():
    profilePath = xbmc.translatePath(plugin.addon.getAddonInfo('profile'))
    xbmcvfs.mkdirs(profilePath)

    mode = plugin.get_setting('external.xmltv')
    if mode == "0":
        return
    if mode == "1":
        path = plugin.get_setting('external.xmltv.file')
    else:
        path = plugin.get_setting('external.xmltv.url')
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
    #TODO check primary key
    conn.execute('CREATE TABLE IF NOT EXISTS streams(name TEXT, tvg_name TEXT, tvg_id TEXT, tvg_logo TEXT, groups TEXT, url TEXT, PRIMARY KEY(name))')
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

    m3uUrl = xbmcaddon.Addon('pvr.iptvsimple').getSetting('m3uUrl')
    if plugin.get_setting('external.m3u') == "1":
        m3uUrl = plugin.get_setting('external.m3u.file')
    elif plugin.get_setting('external.m3u') == "2":
        m3uUrl = plugin.get_setting('external.m3u.url')
    m3uFile = 'special://profile/addon_data/plugin.video.iptv.recorder/channels.m3u'
    xbmcvfs.copy(m3uUrl,m3uFile)
    f = xbmcvfs.File(m3uFile)
    data = f.read()

    channels = re.findall('#EXTINF:(.*?)\n(.*?)\n',data,flags=(re.I|re.DOTALL))
    for channel in channels:
        tvg_name = re.search('tvg-name="(.*?)"',channel[0])
        if tvg_name:
            tvg_name = tvg_name.group(1)
        tvg_id = re.search('tvg-id="(.*?)"',channel[0])
        if tvg_id:
            tvg_id = tvg_id.group(1)
        tvg_logo = re.search('tvg-logo="(.*?)"',channel[0])
        if tvg_logo:
            tvg_logo = tvg_logo.group(1)
        name = channel[0].rsplit(',',1)[-1]
        url = channel[1]
        groups = re.search('group-title="(.*?)"',channel[0])
        if groups:
            groups = groups.group(1)

        conn.execute("INSERT OR IGNORE INTO streams(name,tvg_name,tvg_id,tvg_logo,groups,url ) VALUES(?,?,?,?,?,?)",
        [name,tvg_name,tvg_id,tvg_logo,groups,url])

    conn.commit()
    conn.close()
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

    if plugin.get_setting('debug') == "true":
        items.append(
        {
            'label': "(Re)Load Channel m3u",
            'path': plugin.url_for('m3u'),
            'thumbnail':get_icon_path('settings'),
            'context_menu': context_items,
        })

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
