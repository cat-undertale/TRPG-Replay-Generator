#!/usr/bin/env python
# coding: utf-8
edtion = 'alpha 1.5'

# 外部参数输入

import argparse
import sys
import os

ap = argparse.ArgumentParser(description="Generating your TRPG replay video from logfile.")
ap.add_argument("-l", "--TimeLine", help='Timeline (and break_point with same name), which was generated by replay_generator.py.',type=str)
ap.add_argument("-d", "--MediaObjDefine", help='Definition of the media elements, using real python code.',type=str)
ap.add_argument("-t", "--CharacterTable", help='This program do not need CharacterTable.',type=str)
ap.add_argument("-o", "--OutputPath", help='Choose the destination directory to save the project timeline and break_point file.',type=str,default=None)
# 增加一个，读取时间轴和断点文件的选项！
ap.add_argument("-F", "--FramePerSecond", help='Set the FPS of display, default is 30 fps, larger than this may cause lag.',type=int,default=30)
ap.add_argument("-W", "--Width", help='Set the resolution of display, default is 1920, larger than this may cause lag.',type=int,default=1920)
ap.add_argument("-H", "--Height", help='Set the resolution of display, default is 1080, larger than this may cause lag.',type=int,default=1080)
ap.add_argument("-Z", "--Zorder", help='Set the display order of layers, not recommended to change the values unless necessary!',type=str,
                default='BG3,BG2,BG1,Am3,Am2,Am1,Bb')
args = ap.parse_args()

media_obj = args.MediaObjDefine #媒体对象定义文件的路径
char_tab = args.CharacterTable #角色和媒体对象的对应关系文件的路径
stdin_log = args.TimeLine #log路径
output_path = args.OutputPath #保存的时间轴，断点文件的目录

screen_size = (args.Width,args.Height) #显示的分辨率
frame_rate = args.FramePerSecond #帧率 单位fps
zorder = args.Zorder.split(',') #渲染图层顺序

try:
    for path in [stdin_log,media_obj]:
        if path == None:
            raise OSError("[31m[ArgumentError]:[0m Missing principal input argument!")
        if os.path.isfile(path) == False:
            raise OSError("[31m[ArgumentError]:[0m Cannot find file "+path)

    if output_path == None:
        pass 
    elif os.path.isdir(output_path) == False:
        try:
            os.makedirs(output_path)
        except:
            raise OSError("[31m[SystemError]:[0m Cannot make directory "+output_path)
    output_path = output_path.replace('\\','/')

    # FPS
    if frame_rate <= 0:
        raise ValueError("[31m[ArgumentError]:[0m "+str(frame_rate))
    elif frame_rate>30:
        print("[33m[warning]:[0m",'FPS is set to '+str(frame_rate)+', which may cause lag in the display!')

    if (screen_size[0]<=0) | (screen_size[1]<=0):
        raise ValueError("[31m[ArgumentError]:[0m "+str(screen_size))
    if screen_size[0]*screen_size[1] > 3e6:
        print("[33m[warning]:[0m",'Resolution is set to more than 3M, which may cause lag in the display!')
except Exception as E:
    print(E)
    sys.exit()

# 包导入

import pandas as pd
import numpy as np
from PIL import Image,ImageFont,ImageDraw
import re
import time #开发模式，显示渲染帧率
from pygame import mixer

# 文字对象

outtext_index = 0
clip_index = 0
file_index = 0

class Text:
    def __init__(self,fontfile='C:/Windows/Fonts/simhei.ttf',fontsize=40,color=(0,0,0,255),line_limit=20):
        self.color=color
        self.size=fontsize
        self.line_limit = line_limit
        self.fontpath = fontfile
    def draw(self,text):
        out_text = []
        if ('#' in text) | (text[0]=='^'): #如果有手动指定的换行符
            if text[0]=='^': # 如果使用^指定的手动换行，则先去掉这个字符。
                text = text[1:]
            text_line = text.split('#')
            for tx in text_line:
                out_text.append((tx,self.color,self.fontpath,self.size))
        elif len(text) > self.line_limit: #如果既没有主动指定，字符长度也超限
            for i in range(0,len(text)//self.line_limit+1):
                out_text.append((text[i*self.line_limit:(i+1)*self.line_limit],self.color,self.fontpath,self.size))
        else:
            out_text = [(text,self.color,self.fontpath,self.size)]
        return out_text
    def convert(self):
        pass

    # 对话框、气泡、文本框
class Bubble:
    def __init__(self,filepath,Main_Text=Text(),Header_Text=None,pos=(0,0),mt_pos=(0,0),ht_pos=(0,0),line_distance=1.5):
        global file_index
        self.path = reformat_path(filepath)
        self.MainText = Main_Text
        self.mt_pos = mt_pos
        self.Header = Header_Text
        self.ht_pos = ht_pos
        self.pos = pos
        self.line_distance = line_distance
        self.size = Image.open(filepath).size
        self.filename = self.path.split('/')[-1]
        self.fileindex = 'BGfile_' + '%d'% file_index
        self.PRpos = PR_center_arg(np.array(self.size),np.array(self.pos))
        file_index = file_index+1
    def display(self,begin,end,text,header=''): # 这段代码是完全没有可读性的屎，但是确实可运行，非必要不要改
        global outtext_index,clip_tplt,clip_index
        # 生成文本图片
        ofile = output_path+'/auto_TX_%d'%outtext_index+'.png'
        canvas = Image.new(mode='RGBA',size=self.size,color=(0,0,0,0))
        draw = ImageDraw.Draw(canvas)
        if (self.Header!=None) & (header!=''):    # Header 有定义，且输入文本不为空
            ht_text,color,font,size = self.Header.draw(header)[0]
            font_this = ImageFont.truetype(font, size)
            draw.text(self.ht_pos, ht_text, font = font_this, align ="left",fill = color)
        x,y = self.mt_pos
        for i,s in enumerate(self.MainText.draw(text)):
            mt_text,color,font,size = s
            font_this = ImageFont.truetype(font, size)
            draw.text((x,y+i*self.MainText.size*self.line_distance), mt_text, font = font_this, align ="left",fill = color)
        canvas.save(ofile)
        
        # 生成序列
        width,height = self.size
        pr_horiz,pr_vert = self.PRpos
        clip_bubble = clip_tplt.format(**{'clipid':'BB_clip_%d'%clip_index,
                              'clipname':'BB_clip_%d'%clip_index,
                              'timebase':'%d'%frame_rate,
                              'ntsc':Is_NTSC,
                              'start':'%d'%begin,
                              'end':'%d'%end,
                              'in':'%d'%90000,
                              'out':'%d'%(90000+end-begin),
                              'fileid':self.fileindex,
                              'filename':self.filename,
                              'filepath':self.path,
                              'filewidth':'%d'%width,
                              'fileheight':'%d'%height,
                              'horiz':'%.5f'%pr_horiz,
                              'vert':'%.5f'%pr_vert})
        clip_text = clip_tplt.format(**{'clipid':'TX_clip_%d'%clip_index,
                              'clipname':'TX_clip_%d'%clip_index,
                              'timebase':'%d'%frame_rate,
                              'ntsc':Is_NTSC,
                              'start':'%d'%begin,
                              'end':'%d'%end,
                              'in':'%d'%90000,
                              'out':'%d'%(90000+end-begin),
                              'fileid':'auto_TX_%d'%outtext_index,
                              'filename':'auto_TX_%d.png'%outtext_index,
                              'filepath':reformat_path(ofile),
                              'filewidth':'%d'%width,
                              'fileheight':'%d'%height,
                              'horiz':'%.5f'%pr_horiz,
                              'vert':'%.5f'%pr_vert})

        outtext_index = outtext_index + 1
        clip_index = clip_index+1
        return (clip_bubble,clip_text)

    def convert(self):
        pass

# 背景图片
class Background:
    def __init__(self,filepath,pos = (0,0)):
        global file_index 
        if filepath in cmap.keys(): #对纯色定义的背景的支持
            ofile = output_path+'/auto_BG_'+filepath+'.png'
            Image.new(mode='RGBA',size=screen_size,color=cmap[filepath]).save(ofile)
            self.path = reformat_path(ofile)
            self.size = screen_size
        else:
            self.path = reformat_path(filepath)
            self.size = Image.open(filepath).size
        self.pos = pos
        self.PRpos = PR_center_arg(np.array(self.size),np.array(self.pos))
        self.filename = self.path.split('/')[-1]
        self.fileindex = 'BGfile_%d'% file_index
        file_index = file_index+1
    def display(self,begin,end):
        global clip_tplt,clip_index
        width,height = self.size
        pr_horiz,pr_vert = self.PRpos
        clip_this = clip_tplt.format(**{'clipid':'BG_clip_%d'%clip_index,
                              'clipname':'BG_clip_%d'%clip_index,
                              'timebase':'%d'%frame_rate,
                              'ntsc':Is_NTSC,
                              'start':'%d'%begin,
                              'end':'%d'%end,
                              'in':'%d'%90000,
                              'out':'%d'%(90000+end-begin),
                              'fileid':self.fileindex,
                              'filename':self.filename,
                              'filepath':self.path,
                              'filewidth':'%d'%width,
                              'fileheight':'%d'%height,
                              'horiz':'%.5f'%pr_horiz,
                              'vert':'%.5f'%pr_vert})
        clip_index = clip_index+1
        return clip_this
    def convert(self):
        pass

# 立绘图片
class Animation:
    def __init__(self,filepath,pos = (0,0)):
        global file_index 
        self.path = reformat_path(filepath)
        self.pos = pos
        self.size = Image.open(filepath).size
        self.filename = self.path.split('/')[-1]
        self.fileindex = 'BGfile_%d'% file_index
        self.PRpos = PR_center_arg(np.array(self.size),np.array(self.pos))
        file_index = file_index+1
    def display(self,begin,end):
        global clip_tplt,clip_index
        width,height = self.size
        pr_horiz,pr_vert = self.PRpos
        clip_this = clip_tplt.format(**{'clipid':'AM_clip_%d'%clip_index,
                              'clipname':'AM_clip_%d'%clip_index,
                              'timebase':'%d'%frame_rate,
                              'ntsc':Is_NTSC,
                              'start':'%d'%begin,
                              'end':'%d'%end,
                              'in':'%d'%90000,
                              'out':'%d'%(90000+end-begin),
                              'fileid':self.fileindex,
                              'filename':self.filename,
                              'filepath':self.path,
                              'filewidth':'%d'%width,
                              'fileheight':'%d'%height,
                              'horiz':'%.5f'%pr_horiz,
                              'vert':'%.5f'%pr_vert})
        clip_index = clip_index+1
        return clip_this
    def convert(self):
        pass

# 音效
class Audio:
    def __init__(self,filepath):
        global file_index 
        self.path = reformat_path(filepath)
        self.length = get_audio_length(filepath)*frame_rate
        self.filename = self.path.split('/')[-1]
        self.fileindex = 'AUfile_%d'% file_index
        file_index = file_index+1
        
    def display(self,begin):
        global audio_clip_tplt,clip_index
        clip_this = audio_clip_tplt.format(**{'clipid':'AU_clip_%d'%clip_index,
                                              'type':Audio_type,
                                              'clipname':'AU_clip_%d'%clip_index,
                                              'audiolen':'%d'%self.length,
                                              'timebase':'%d'%frame_rate,
                                              'ntsc':Is_NTSC,
                                              'start':'%d'%begin,
                                              'end':'%d'%(begin+self.length),
                                              'in':'0',
                                              'out':'%d'%self.length,
                                              'fileid':self.fileindex,
                                              'filename':self.filename,
                                              'filepath':self.path})
        clip_index = clip_index+1
        return clip_this
    
    def convert(self):
        pass

# 背景音乐
class BGM:
    def __init__(self,filepath,volume=100,loop=True):
        print('[33m[warning]:[0m BGM '+filepath+' is automatically ignored, you should add BGM manually in Premiere Pro later.')
    def convert(self):
        pass

# 函数定义

# 获取音频长度
def get_audio_length(filepath):
    mixer.init()
    try:
        this_audio = mixer.Sound(filepath)
    except Exception as E:
        print('[33m[warning]:[0m Unable to get audio length of '+str(filepath)+', due to:',E)
        return np.nan
    return this_audio.get_length()

# 重格式化路径
def reformat_path(path):#only use for windows path format
    cwd = os.getcwd().replace('\\','/')
    if path[0] == '/': #unix正斜杠，报错
        raise ValueError('invalid path type')
    if '\\' in path: #是不是反斜杠？
        path.replace('\\','/') 
    if path[0] == '.':#是不是./123/型
        path = cwd + path[1:]
    if path[0:2] not in ['C:','D:','E:','F:','G:','H:']: #是不是123/型
        path = cwd + '/' + path
    disk_label = path[0]
    path = path.replace('//','/')
    return 'file://localhost/' + disk_label + '%3a' + path[path.find('/'):]

# 处理bg 和 am 的parser
def parse_timeline(layer):
    global timeline,break_point
    track = timeline[[layer]]
    clips = []
    item,begin,end = 'NA',0,0
    for key,values in track.iterrows():
        #如果item变化了，或者进入了指定的断点
        if (values[layer] != item) | (key in break_point.values): 
            if (item == 'NA') | (item!=item): # 如果itme是空 
                pass # 则不输出什么
            else:
                end = key #否则把当前key作为一个clip的断点
                clips.append((item,begin,end)) #并记录下这个断点
            item = values[layer] #无论如何，重设item和begin
            begin = key
        else: #如果不满足断点要求，那么就什么都不做
            pass
    # 循环结束之后，最后检定一次是否需要输出一个clips
    end = key
    if (item == 'NA') | (item!=item):
        pass
    else:
        clips.append((item,begin,end))
    return clips #返回一个clip的列表

# 处理Bb 的parser
def parse_timeline_bubble(layer):
    global timeline,break_point
    track = timeline[[layer,layer+'_main',layer+'_header']]
    clips = []
    item,begin,end = 'NA',0,0
    for key,values in track.iterrows():
        #如果item变化了，或者进入了指定的断点(这是保证断句的关键！)
        if (values[layer] != item) | (key in break_point.values): 
            if (item == 'NA') | (item!=item): # 如果itme是空 
                pass # 则不输出什么
            else:
                end = key #否则把当前key作为一个clip的断点
                clips.append((item,main_text,header_text,begin,end)) #并记录下这个断点
            item = values[layer] #无论如何，重设item和begin
            main_text = values[layer + '_main']
            header_text = values[layer + '_header']
            begin = key
        else: #如果不满足断点要求，那么就什么都不做
            pass
        # 然后更新文本内容
        main_text = values[layer + '_main']
        header_text = values[layer + '_header']
    # 循环结束之后，最后检定一次是否需要输出一个clips
    end = key
    if (item == 'NA') | (item!=item):
        pass
    else:
        clips.append((item,main_text,header_text,begin,end))
    return clips #返回一个clip的列表

# pygame形式的pos转换为PR形式的pos

def PR_center_arg(obj_size,pygame_pos):
    screensize = np.array(screen_size)
    return (pygame_pos+obj_size/2-screensize/2)/obj_size

# 全局变量

cmap = {'black':(0,0,0,255),'white':(255,255,255,255),'greenscreen':(0,177,64,255)}
Is_NTSC = str(frame_rate % 30 == 0)
Audio_type = 'Stereo'
stdin_name = stdin_log.replace('\\','/').split('/')[-1]

# 载入xml 模板文件

project_tplt = open('./xml_templates/tplt_sequence.xml','r',encoding='utf8').read()
track_tplt = open('./xml_templates/tplt_track.xml','r',encoding='utf8').read()
audio_track_tplt = open('./xml_templates/tplt_audiotrack.xml','r',encoding='utf8').read()
clip_tplt = open('./xml_templates/tplt_clip.xml','r',encoding='utf8').read()
audio_clip_tplt = open('./xml_templates/tplt_audio_clip.xml','r',encoding='utf8').read()

# 载入timeline 和 breakpoint

timeline = pd.read_pickle(stdin_log)
break_point = pd.read_pickle(stdin_log.replace('timeline','breakpoint'))

def main():
    # 载入od文件
    global media_list
    print('[export XML]: Welcome to use exportXML for TRPG-replay-generator '+edtion)
    print('[export XML]: The output xml file and refered png files will be saved at "'+output_path+'"')

    object_define_text = open(media_obj,'r',encoding='utf-8').read().split('\n')
    media_list=[]
    for i,text in enumerate(object_define_text):
        if text == '':
            continue
        elif text[0] == '#':
            continue
        else:
            try:
                exec(text) #对象实例化
                obj_name = text.split('=')[0]
                obj_name = obj_name.replace(' ','')
                media_list.append(obj_name) #记录新增对象名称
            except Exception as E:
                print('[31m[SyntaxError]:[0m "'+text+'" appeared in media define file line ' + str(i+1)+' is invalid syntax.')
                sys.exit()
    black = Background('black')
    white = Background('white')
    media_list.append('black')
    media_list.append('white')
    #print(media_list)

    # 开始生成

    print('[export XML]: Begin to export.')
    video_tracks = []
    audio_tracks = []
    for layer in zorder + ['SE','Voice']:
        if layer == 'Bb':
            track_items = parse_timeline_bubble(layer)
            bubble_clip_list = []
            text_clip_list = []
            for item in track_items:
                bubble_this,text_this = eval('{0}.display(begin ={1},end={2},text="{3}",header="{4}")'
                                             .format(item[0],item[3],item[4],item[1],item[2]))
                bubble_clip_list.append(bubble_this)
                text_clip_list.append(text_this)
            video_tracks.append(track_tplt.format(**{'targeted':'False','clips':'\n'.join(bubble_clip_list)}))
            video_tracks.append(track_tplt.format(**{'targeted':'True','clips':'\n'.join(text_clip_list)}))
            
        elif layer in ['SE','Voice']:
            track_items = parse_timeline(layer)
            clip_list = []
            for item in track_items:
                if item[0] in media_list:
                    clip_list.append(eval('{0}.display(begin={1})'.format(item[0],item[1])))
                elif os.path.isfile(item[0][1:-1]) == True: # 注意这个位置的item[0]首尾应该有个引号
                    temp = Audio(item[0][1:-1])
                    clip_list.append(temp.display(begin=item[1]))
                else:
                    print("[33m[warning]:[0m",'Audio file',item[0],'is not exist.')
            audio_tracks.append(audio_track_tplt.format(**{'type':Audio_type,'clips':'\n'.join(clip_list)}))
            
        else:
            track_items = parse_timeline(layer)
            clip_list = []
            for item in track_items:
                clip_list.append(eval('{0}.display(begin={1},end={2})'.format(item[0],item[1],item[2])))
            video_tracks.append(track_tplt.format(**{'targeted':'False','clips':'\n'.join(clip_list)}))

    main_output = project_tplt.format(**{'timebase':'%d'%frame_rate,
                           'ntsc':Is_NTSC,
                           'sequence_name':stdin_name,
                           'screen_width':'%d'%screen_size[0],
                           'screen_height':'%d'%screen_size[1],
                           'tracks_vedio':'\n'.join(video_tracks),
                           'tracks_audio':'\n'.join(audio_tracks)})

    ofile = open(output_path+'/'+stdin_name+'.xml','w')
    ofile.write(main_output)
    ofile.close()
    print('[export XML]: Done!')

if __name__ == '__main__':
    main()