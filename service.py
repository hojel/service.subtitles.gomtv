# -*- coding: utf-8 -*- 

import sys
import os
import xbmc
import urllib, urllib2
import xbmcvfs
import xbmcaddon
import xbmcgui
import xbmcplugin
import re
import shutil
import unicodedata
from hashlib import md5
from BeautifulSoup import BeautifulSoup

__addon__ = xbmcaddon.Addon()
__scriptid__   = __addon__.getAddonInfo('id')

__cwd__        = xbmc.translatePath( __addon__.getAddonInfo('path') ).decode("utf-8")
__profile__    = xbmc.translatePath( __addon__.getAddonInfo('profile') ).decode("utf-8")
__resource__   = xbmc.translatePath( os.path.join( __cwd__, 'resources', 'lib' ) ).decode("utf-8")
__temp__       = xbmc.translatePath( os.path.join( __profile__, 'temp') ).decode("utf-8")

sys.path.append (__resource__)

from smi2ass import smi2ass

ROOT_URL   = "http://gom.gomtv.com"
USER_AGENT = "GomPlayer 2, 1, 23, 5007 (KOR)"

ENG_TITLE_PTN = re.compile("^(.*)\(([^\)]*)\)$")
JAMAK_TITLE_PTN = re.compile("<h4>([^<]*)</h4>")
JAMAK_ID_PTN = re.compile('name="intseq" +value="(\d+)"')

###################################################################################
def Search( item ):
    convertASS = (__addon__.getSetting("convertASS") == "true")

    xbmc.log("Search GomTV with a file name, "+item['file_original_path'].encode('cp949', 'ignore'), level=xbmc.LOGDEBUG)
    video_hash = hashFileMD5( item['file_original_path'], buff_size=1024*1024 )
    if video_hash is None:
        xbmc.log(u"Fail to access movie flie, "+item['file_original_path'].encode('cp949', 'ignore'), level=xbmc.LOGERROR)
        return

    q_url = "http://gom.gomtv.com/jmdb/search.html?key=%s" %video_hash
    subtitles_list = SearchSubtitles( q_url )

    if not subtitles_list:
        xbmc.log("No result with hash, "+video_hash, level=xbmc.LOGNOTICE)
        if item['tvshow']:
            search_string = ("%s S%.2dE%.2d" %
                (item['tvshow'], int(item['season']), int(item['episode']))).replace(" ","+")
        else:
            if str(item['year']) == "":
                item['title'], item['year'] = xbmc.getCleanMovieTitle( item['title'] )
            # use English title if available
            query = ENG_TITLE_PTN.match(item['title'])
            srch_title = query.group(2).strip() if query else item['title']
            search_string = srch_title.replace(" ","+")

        q_url = "http://gom.gomtv.com/main/index.html?ch=subtitles&pt=l&menu=subtitles&lang=0&sValue=%s" %search_string
        subtitles_list = SearchSubtitles( q_url )

    xbmc.log("Found %d subtitles in GomTV" %len(subtitles_list), level=xbmc.LOGINFO)
    for sub in subtitles_list:
        listitem = xbmcgui.ListItem(
                        label=sub['language_name'],
                        label2=sub['filename'],
                        iconImage=sub['rating'],
                        thumbnailImage=sub['language_flag'],
                    )
        listitem.setProperty("sync", 'true' if sub["sync"] else 'false')
        listitem.setProperty("hearing_imp", 'true' if sub.get("hearing_imp", False) else 'false')

        url = "plugin://%s/?action=download&link=%s&ID=%s&filename=%s&format=%s" % (__scriptid__,
                            urllib.quote(sub["link"]),
                            sub["ID"],
                            sub["filename"],
                            'ass' if convertASS else sub["format"]
                            )
        xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=url, listitem=listitem, isFolder=False)

def Download (sub_id, link, filename, sub_fmt):
    if xbmcvfs.exists(__temp__):
        shutil.rmtree(__temp__)
    xbmcvfs.mkdirs(__temp__)

    url = GetSubtitleUrl( link )
    xbmc.log("download subtitle from %s" %url, level=xbmc.LOGINFO)
    subtitle_list = []

    # only one file to download
    try:
        smi_sgml = urllib.urlopen(url).read()
    except:
        xbmc.log("fail to download subtitle from %s" %url, level=xbmc.LOGWARNING)
        return []

    # convert to ASS format
    if sub_fmt == 'ass':
        assDict = smi2ass( smi_sgml )
        if len(assDict) > 1 and 'Korean' in assDict:    # select Korean in multi-language
            lang = 'Korean'
        else:
            lang = assDict.keys()[0]
        sub_txt = assDict[lang]
    else:
        sub_txt = smi_sgml

    # store in temp
    subtitle = os.path.join(__temp__, "%s.%s" %(sub_id, sub_fmt))
    with open(subtitle, "w") as subFile:
        subFile.write( sub_txt )
    subFile.close()
    subtitle_list.append(subtitle)
    xbmc.log("stored at "+subtitle.encode('cp949', 'ignore'), xbmc.LOGINFO)

    if xbmcvfs.exists(subtitle_list[0]):
        return subtitle_list

def hashFileMD5(file_path, buff_size=1048576):
    # calculate MD5 key from file
    f = xbmcvfs.File(file_path)
    if f.size() < buff_size:
        return None
    f.seek(0,0)
    buff = f.read(buff_size)    # size=1M
    f.close()
    # calculate MD5 key from file
    m = md5();
    m.update(buff);
    return m.hexdigest()
  
###################################################################################
def SearchSubtitles(q_url):
    xbmc.log("search subtitle at %s"  %q_url, level=xbmc.LOGDEBUG)

    # main page
    req = urllib2.Request(q_url)
    req.add_header("User-Agent", USER_AGENT)
    html = urllib2.urlopen(req).read()
    if "<div id='search_failed_smi'>" in html:
        xbmc.log("no result found", level=xbmc.LOGINFO)
        return []
    elif "<script>location.href" in html or "<script>top.location.replace" in html:
        xbmc.log("redirected", level=xbmc.LOGINFO)
        if "key=';</script>" in html:
            xbmc.log("fail to search with given key", level=xbmc.LOGNOTICE)
            return []
        url = parseRedirectionPage(html)
        req = urllib2.Request(url)
        req.add_header("User-Agent", USER_AGENT)
        resp = urllib2.urlopen(req)
        html = resp.read()
        # if only one subtitle exists, redirected directly
        new_url = resp.geturl()
        if '&seq=' in new_url:
            xbmc.log("Redirect to "+url, xbmc.LOGINFO)
            title = JAMAK_TITLE_PTN.search(html).group(1)
            sub_id = JAMAK_ID_PTN.search(html).group(1)
            return [ {
                "link"          : new_url,
                "filename"      : title,
                "ID"            : sub_id,
                "format"        : "smi",
                "sync"          : True,
                "rating"        : "0",
                "language_name" : 'Korean',
                "language_flag" : 'ko'
            } ]            

    # regular search result page
    soup = BeautifulSoup(html)
    subtitles = []
    for row in soup.find("table",{"class":"tbl_lst"}).findAll("tr")[1:]:
        a_node = row.find("a")
        if a_node is None:
            continue
        title = a_node.text
        sub_id = row.find("span",{"class":"txt_clr1"}).string
        lang_node_string = row.find("span",{"class":"txt_clr3"}).string
        url = ROOT_URL + a_node["href"]
        if u"한글" in lang_node_string:
            langlong  = "Korean"
            langshort = "ko"
        elif u"영문" in lang_node_string:
            langlong  = "English"
            langshort = "en"
        else:   # [통합]
            langlong  = "Korean"
            langshort = "ko"
        subtitles.append( {
            "link"          : url,
            "filename"      : title,
            "ID"            : sub_id,
            "format"        : "smi",
            "sync"          : True,
            "rating"        : "0",
            "language_name" : langlong,
            "language_flag" : langshort
        } )            

    return subtitles

def parseRedirectionPage(html):
    url = re.split("\'",html)[1]
    if 'noResult' in url:   # no result (old style)
        xbmc.log("Unusual result page, "+page_url, level=xbmc.LOGWARNING)
        return subtitles
    return ROOT_URL+url

def GetSubtitleUrl(page_url):
    html = urllib.urlopen(page_url).read()
    sp2 = ""
    if "a href=\"jamak://gom.gomtv.com" in html:
        sp = re.split("a href=\"jamak://gom.gomtv.com",html)[1]
        sp2 = re.split("\"",sp)[0]
    elif "onclick=\"downJm(" in html:
        s1 = re.split("onclick=\"downJm",html)[1]
        intSeq = re.split("'",s1)[1]
        capSeq = re.split("'",s1)[3]
        sp2 = "/main/index.html?pt=down&ch=subtitles&intSeq="+intSeq+"&capSeq="+capSeq
    else:
        return None
    return ROOT_URL+sp2

###################################################################################
def normalizeString(str):
    return unicodedata.normalize('NFKD', unicode(unicode(str, 'utf-8'))).encode('ascii', 'ignore')

def get_params():
    param = []
    paramstring = sys.argv[2]
    if len(paramstring) >= 2:
        params = paramstring
        cleanedparams = params.replace('?', '')
        if (params[len(params)-1]=='/'):
            params=params[0:len(params)-2]
        pairsofparams=cleanedparams.split('&')
        param = {}
        for i in range(len(pairsofparams)):
            splitparams={}
            splitparams=pairsofparams[i].split('=')
            if (len(splitparams))==2:
                param[splitparams[0]]=splitparams[1]

    return param

# Get parameters from XBMC and launch actions
params = get_params()

if params['action'] == 'search':
    item = {}
    item['temp']               = False
    item['rar']                = False
    item['year']               = xbmc.getInfoLabel("VideoPlayer.Year")                           # Year
    item['season']             = str(xbmc.getInfoLabel("VideoPlayer.Season"))                    # Season
    item['episode']            = str(xbmc.getInfoLabel("VideoPlayer.Episode"))                   # Episode
    item['tvshow']             = normalizeString(xbmc.getInfoLabel("VideoPlayer.TVshowtitle"))   # Show
    item['title']              = normalizeString(xbmc.getInfoLabel("VideoPlayer.OriginalTitle")) # try to get original title
    item['file_original_path'] = urllib.unquote(xbmc.Player().getPlayingFile().decode('utf-8'))  # Full path of a playing file
    item['3let_language']      = []
    item['2let_language']      = []

    for lang in urllib.unquote(params['languages']).decode('utf-8').split(","):
        item['3let_language'].append(xbmc.convertLanguage(lang, xbmc.ISO_639_2))
        item['2let_language'].append(xbmc.convertLanguage(lang, xbmc.ISO_639_1))

    if not item['title']:
        # no original title, get just Title
        item['title']  = normalizeString(xbmc.getInfoLabel("VideoPlayer.Title"))

    if "s" in item['episode'].lower():
        # Check if season is "Special"
        item['season'] = "0"
        item['episode'] = item['episode'][-1:]

    if "http" in item['file_original_path']:
        item['temp'] = True

    elif "rar://" in item['file_original_path']:
        item['rar'] = True
        item['file_original_path'] = os.path.dirname(item['file_original_path'][6:])

    elif "stack://" in item['file_original_path']:
        stackPath = item['file_original_path'].split(" , ")
        item['file_original_path'] = stackPath[0][8:]

    Search(item)

elif params['action'] == 'download':
    # we pickup all our arguments sent from def Search()
    subs = Download(params["ID"], urllib.unquote(params["link"]), params["filename"], params["format"])
    # we can return more than one subtitle for multi CD versions, for now we
    # are still working out how to handle that in XBMC core
    for sub in subs:
        listitem = xbmcgui.ListItem(label=sub)
        xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=sub, listitem=listitem, isFolder=False)

# Send end of directory to XBMC
xbmcplugin.endOfDirectory(int(sys.argv[1]))
