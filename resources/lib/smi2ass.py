# -*- coding: UTF-8 -*-

import os, sys, re
from collections import defaultdict
from operator import itemgetter
from BeautifulSoup import BeautifulSoup
from asscontents import *


def smi2ass(smi_sgml):
    # check character encoding and covert to UTF-8
    smi_sgml = chdetToUTF8(smi_sgml) 
    
    #Parse lines with BeautifulSoup based on sync tag
    pool = BeautifulSoup(smi_sgml, fromEncoding='utf-8')
    smiLines = pool.findAll('sync')

    #separate multi-language subtitle into a sperate list
    mln, longlang= multiLanguageSeperation(smiLines)
    assDict = {}
    for langIndex, lang in enumerate(mln):
        asslines = smiToassSynax (mln[lang])
        if len(asslines) > 0:
            
            asscontents = (scriptInfo+styles+events+''.join(asslines)).encode('utf8')
            assDict[longlang[langIndex]] = asscontents 
    return assDict
        
def smiToassSynax (sln):
    asslines = []
    for lineIndex, item in enumerate(sln):
        try: # bad cases : '<SYNC .','<SYNC Start=479501??>' 
            li = sln[lineIndex]['start']
            li1 = sln[lineIndex+1]['start']
        except :
            #print ml[lang][lineIndex]
            li = None
            li1 = None
        if lineIndex + 1 < len(sln) and not li == None and not li1 == None:
            tcstart = ms2timecode(int(item['start']))
            tcend = ms2timecode(int(sln[lineIndex+1]['start']))
            
            pTag = item.find('p')# <SYNC Start=41991><P Class=KRCC><SYNC Start=43792><P Class=KRCC>
            br = pTag.findAll('br')
            if len(pTag.text)>1:
                for gg in br:
                    gg.replaceWith('\N')
            else:# bad cases : <SYNC Start=305920><P Class=KRCC><br>
                for gg in br:
                    gg.replaceWith('')
                
            bold = pTag.findAll('b')
            for bo in bold:
                boldre = '{\\b1}'+bo.text+'{\\b0}'
                bo.replaceWith(boldre)
                
            italics = pTag.findAll('i')
            for it in italics:
                itre = '{\\i1}'+it.text+'{\\i0}'
                it.replaceWith(itre)

            underlines = pTag.findAll('u')
            for un in underlines:
                unre = '{\\u1}'+un.text+'{\\u0}'
                un.replaceWith(unre)

            strikes = pTag.findAll('s')
            for st in strikes:
                stre = '{\\s1}'+st.text+'{\\s0}'
                st.replaceWith(stre)

            colors = pTag.findAll('font')
            for color in colors:
                try: # bad cases : '<font size=30>'
                    col = color['color']
                except:
                    col = None
                if not col == None:
                    hexcolor = re.search('[0-9a-fA-F]{6}',color['color'].lower()) # bad cases : '23df34'
                    if hexcolor is not None:
                        colorCovt = '{\c&H' + hexcolor.group(0)[::-1]+'&}'+ color.text + '{\c}'
                    else:
                        try:
                            colorCovt = '{\c&H' + css3_names_to_hex[color['color'].lower()][::-1].replace('#','&}')+ color.text + '{\c}'
                        except: # bad cases : 'skybule'
                            colorCovt = color.text
                            print color['color'].lower()
                    color.replaceWith(colorCovt)
                
            contents = re.sub(r'&nbsp;', '', pTag.text)
            contents = re.sub(r'\s+', ' ', contents)
            if not contents == '':
                line = 'Dialogue: 0,%s,%s,Default,,0000,0000,0000,,%s\n' % (tcstart,tcend, contents)
                asslines.append(line)
    return asslines
 
def chdetToUTF8(aBuf):
        # If the data starts with BOM, we know it is UTF
    if aBuf[:3] == '\xEF\xBB\xBF':
        # EF BB BF  UTF-8 with BOM
        result = "UTF-8"
    elif aBuf[:2] == '\xFF\xFE':
        # FF FE  UTF-16, little endian BOM
        result = "UTF-16LE"
    elif aBuf[:2] == '\xFE\xFF':
        # FE FF  UTF-16, big endian BOM
        result = "UTF-16BE"
    elif aBuf[:4] == '\xFF\xFE\x00\x00':
        # FF FE 00 00  UTF-32, little-endian BOM
        result = "UTF-32LE"
    elif aBuf[:4] == '\x00\x00\xFE\xFF': 
        # 00 00 FE FF  UTF-32, big-endian BOM
        result = "UTF-32BE"
    elif aBuf[:4] == '\xFE\xFF\x00\x00':
        # FE FF 00 00  UCS-4, unusual octet order BOM (3412)
        result = "X-ISO-10646-UCS-4-3412"
    elif aBuf[:4] == '\x00\x00\xFF\xFE':
        # 00 00 FF FE  UCS-4, unusual octet order BOM (2143)
        result = "X-ISO-10646-UCS-4-2143"
    else:
        result = "CP949"
    if result != 'UTF-8':
        # there are a few case where illegal chars included for CP949 and UTF-16LE, just ignore those
        aBuf = unicode(aBuf, result.lower(),'ignore').encode('utf-8')
    return aBuf
        


def ms2timecode(ms):
    hours = ms / 3600000L
    ms -= hours * 3600000L
    minutes = ms / 60000L
    ms -= minutes * 60000L
    seconds = ms / 1000L
    ms -= seconds * 1000L
    ms = round(ms/10)
    timecode = '%01d:%02d:%02d.%02d' % (hours, minutes, seconds, ms)
    return timecode


def multiLanguageSeperation(smiLines):

    #prepare multilanguage dict with languages separated list
    multiLanguageDict = defaultdict(list)
    
    #loop for number of smi subtitle lines
    for lineIndex, subtitleLine in enumerate(smiLines):
        #print lineIndex
        
        #get time code from start tag
        try:
            timeCode = int(subtitleLine['start'])
        except:
            print subtitleLine
        
        #get language name from p tag
        try:
            languageTag = subtitleLine.find('p')['class']
        except:
            print subtitleLine
        
        # seperate langs depending on p class (language tag)
        # put smiLine,  Line Index, and time code into list (ml is dictionary (key is language name from p tag) with lists) 
        try:
            multiLanguageDict[languageTag].append([subtitleLine,lineIndex,timeCode])
        except: # bad cases : '<SYNC Start=7630><P>'
            try: # if no p class name, add unknown as language tag and handle later
                #languageTag = smiLines[lineIndex-1].find('p')['class']
                multiLanguageDict['unknown'].append([subtitleLine,lineIndex,timeCode])
            except:
                pass

    # check whether proper multiple language subtitle
    # if one language is less than 10% of the other language,
    # it is likely that misuse of class name
    # so combine or get rid of them

    # get number of lines for each langauge and sort with number of lines
    langcodes = multiLanguageDict.keys()
    langcount=[]
    for lang in langcodes:
        langcount.append([lang, len(multiLanguageDict[lang])])
    langcount = sorted(langcount, key=itemgetter(1))
    
    # calculate % of each language from largest, put it in langcount
    languageTagCheckFlag = 0
    for index, lang in enumerate(langcount):
        portion = float(len(multiLanguageDict[lang[0]]))/float(langcount[len(langcount)-1][1])
        langcount[index].insert(2,float(len(multiLanguageDict[lang[0]]))/float(langcount[len(langcount)-1][1]))
        try:
            langName = langCode[langcount[index][0].upper()]
            langCnvt = 1
        except:
            langName = langcount[index][0].upper()
            langCnvt = 0
        langcount[index].insert(3,langName)
        langcount[index].insert(4,langCnvt)
        if portion < 0.1:
            langcount[index].insert(5,1)
            languageTagCheckFlag = languageTagCheckFlag +1
        else:
            langcount[index].insert(5,0)
    
    # if there is a language with less than 10%, only two language exist than combine them
    if languageTagCheckFlag > 0 and len(langcount) == 2:
        tempml = multiLanguageDict[langcount[0][0]]
        for tr in tempml:
            multiLanguageDict[langcount[1][0]].append(tr)
        del multiLanguageDict[langcount[0][0]]
    
    # covert to real language name and merge to largest    
    elif languageTagCheckFlag > 1 :
        for index, langc in enumerate(langcount):
            if langc[5] == 1 and langc[4] == 1: # less than 10% and coverted to real lang name
                toBeMergedLangName = langc[3]
                # find largest one with same language name
                for lg in range(len(langcount)-1,0, -1):
                    if langcount[lg][3] == toBeMergedLangName:
                        largestSameName = lg
                        break
                # merge to largest 
                tempml = multiLanguageDict[langcount[index][0]]
                for tr in tempml:
                    multiLanguageDict[langcount[largestSameName][0]].append(tr)
                del multiLanguageDict[langcount[index][0]]
            # if p language Tag is not coverted to real language name, just get rid of it.
            elif langc[5] == 1and langc[4] == 0:
                del multiLanguageDict[langcount[index][0]]
        
    #good to sort based on timecode before processing
    multiLanguageDictSorted = defaultdict(list)
    for lng in multiLanguageDict:
        temp_ml = sorted(multiLanguageDict[lng], key=itemgetter(2))
        for te in temp_ml:
            multiLanguageDictSorted[lng].append(te[0])
    
    #covert p tag language to long language name for ASS file name
    longlang=[]    
    for lang in multiLanguageDictSorted:
        if len(multiLanguageDictSorted)>1:
            try :
                if langCode[lang.upper()] in longlang:
                    longlang.append(lang)
                else:
                    longlang.append(langCode[lang.upper()])
            except:
                longlang.append(lang)
        else:
            longlang.append('')
    return multiLanguageDictSorted, longlang

if __name__ == '__main__':
    smi_file = xbmcvfs.File("badcase.smi","r")
    smi_sgml = smi_file.read()
    smi_file.close()
    assDict = smi2ass(smi_sgml)
    for lang in assDict:
        assPath = smiPath[:smiPath.rfind('.')]+'.'+lang+'.ass'
        assfile= open(assPath, "w")
        assfile.write(assDict[lang])
        assfile.close()

