#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import os
import subprocess
import sys
import shutil
import argparse
import cv2
import numpy as np
import re  # 新增：用于正则匹配，实现自然排序
import sys

# 获取当前操作系统标识
if sys.platform == "darwin":
    os_cmd = "magick"
else:
    os_cmd = "convert" # 默认使用 ImageMagick 的 convert 命令


isDebug = False
needZip = False
outputVideoPath = ""
imageDir = ""
srcPath = ""
maskPath = ""
outputPath = ""
oVideoFilePath = ""

fps = 25
bitrate = 2000

def main():
    parser = argparse.ArgumentParser(description='manual to this script')
    parser.add_argument('--file', type=str, default = None)
    parser.add_argument('--dir', type=str, default = None)
    parser.add_argument('--zip', type=str2bool, nargs='?', const=True, default = False, help="Activate zip mode.")
    parser.add_argument('--fps', type=int, default = 25)
    parser.add_argument('--bitrate', type=int, default = 2000)
    args = parser.parse_args()

    print("convertAlphaVideo.py running")

    global needZip, fps, bitrate
    needZip = args.zip
    fps = args.fps
    bitrate = args.bitrate

    print("args.zip: ", args.zip)
    
    if not args.file is None:
        parseVideoFile(args.file)
    elif not args.dir is None:
        parseImageDir(args.dir)
    else:
        print("params is None!")
        return
    print("finish")

def str2bool(v):
    if isinstance(v, bool):
       return v
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')

def help():
    print("help ~")

# --- 新增辅助函数：自然排序 ---
def natural_sort_key(s):
    """
    将字符串拆分为文本和数字块，实现自然排序。
    例如：['file1.png', 'file10.png', 'file2.png'] 
    排序后变为 ['file1.png', 'file2.png', 'file10.png']
    """
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split('([0-9]+)', s)]

def parseVideoFile(path):
    print(">>>>>>> paraseVideoFile, file is %s" % path)

    basename = os.path.basename(path)
    basename = basename.split('.')[0]
    parentDir = basename + "/"

    initDir(parentDir)
    # 视频拆帧产生的本来就是规范的 %05d.png，所以这里处理相对简单
    # 但为了统一逻辑，parseImageList 依然会执行标准化重命名
    videoToImage(path, imageDir, basename) 
    parseImageList(imageDir)

    # 由于 parseImageList 已经将 output 目录下的文件标准化为 00000.jpg 格式
    # 这里直接使用标准 pattern 即可
    name_pattern = "%05d.jpg"
    imagesToVideo(outputPath, oVideoFilePath, name_pattern)

    shutil.rmtree(parentDir + "temp/")
    print(">>>>>> convert alpha video finish, video file path is : %s" % oVideoFilePath)

def parseImageDir(path):
    parentDir = os.path.abspath(path) + "/"
    print(">>>>>>> paraseImageDir, dirName is %s" % parentDir)

    initDir(parentDir)
    
    # 核心逻辑都在这里面了
    parseImageList(parentDir)

    # --- 逻辑优化 ---
    # 不需要再去扫描 output 目录猜文件名了。
    # 因为 parseImageList 已经强制把生成的图片重命名为 00000.jpg, 00001.jpg ...
    # 所以直接使用固定的 pattern
    
    print("Using standard sequence pattern for video generation.")
    name_pattern = "%05d.jpg" 
    imagesToVideo(outputPath, oVideoFilePath, name_pattern)

    shutil.rmtree(parentDir + "temp/")
    print(">>>>>> convert alpha video finish, video file path is : %s" % oVideoFilePath)

def initDir(parentDir):
    global imageDir, srcPath, maskPath, outputPath, outputVideoPath, oVideoFilePath
    imageDir = parentDir + "temp/imageDir/"
    mkdir(imageDir)
    srcPath = parentDir + "temp/source/"
    mkdir(srcPath)
    maskPath = parentDir + "temp/mask/"
    mkdir(maskPath)
    outputPath = parentDir + "temp/output/"
    mkdir(outputPath)
    outputVideoPath = parentDir + "output/"
    mkdir(outputVideoPath)

    oVideoFilePath = outputVideoPath + "video.mp4"

def parseImageList(inputPath):
    """
    读取源文件夹，进行自然排序，处理图片，并将结果按顺序保存为标准化的数字文件名。
    """
    fileList = os.listdir(inputPath)
    
    # 1. 过滤：只保留 PNG 文件 (防止 .DS_Store 或其他杂文件干扰)
    png_files = [f for f in fileList if f.lower().endswith('.png')]
    
    # 2. 排序：使用自然排序，解决 "1, 10, 2" 乱序问题
    png_files.sort(key=natural_sort_key)
    
    totalLength = len(png_files)
    
    if totalLength == 0:
        print("Error: No png files found in %s" % inputPath)
        return

    print(f"Found {totalLength} images. Processing sequentially...")

    # 3. 遍历处理并重命名
    for index, fileName in enumerate(png_files):
        inputImageFile = os.path.join(inputPath, fileName)
        
        # 获取文件名（不含后缀），用于临时文件（虽然临时文件也可以标准化，但保留原名方便debug）
        baseNameNoExt = os.path.splitext(fileName)[0]
        
        srcImageFile = os.path.join(srcPath, baseNameNoExt + ".jpg")
        tempMaskImageFile = os.path.join(maskPath, baseNameNoExt + "_temp.jpg")
        maskImageFile = os.path.join(maskPath, baseNameNoExt + ".jpg")
        
        # --- 关键修改 ---
        # 无论原文件名是什么（含空格、中文、乱码），
        # 输出文件强制命名为 5位数字.jpg (00000.jpg, 00001.jpg)
        # 这样 ffmpeg 读取时永远不会出错
        outputImageFile = os.path.join(outputPath, "%05d.jpg" % index)

        removeAlpha(inputImageFile, srcImageFile)
        if needZip:
            separateAlphaChannel(inputImageFile, tempMaskImageFile)
            zipAlphaChannelPro(tempMaskImageFile, maskImageFile)
        else:
            separateAlphaChannel(inputImageFile, maskImageFile)
        
        appendImageLand(srcImageFile, maskImageFile, outputImageFile)

        deleteTempFile(srcImageFile)
        deleteTempFile(maskImageFile)
        deleteTempFile(tempMaskImageFile)

        updateProgress(index + 1, totalLength)
    
    print("\nImages processed and renormalized to sequence 00000.jpg - %05d.jpg" % (totalLength - 1))

def videoToImage(videoPath, imageDir, basename=None):
    # 视频拆帧保持原样即可，这里拆出来的文件名本身就很规范
    if basename:
        image_sequence_specifier = os.path.join(imageDir, basename + "%05d.png")
    else:
        image_sequence_specifier = os.path.join(imageDir, "%05d.png")
    
    # 使用双引号包裹路径，防止视频文件名中有空格导致 ffmpeg 报错
    command = 'ffmpeg -i "{}" -r {} "{}"'.format(videoPath, fps, image_sequence_specifier)
    if isDebug:
        print(command)
    ret = subprocess.Popen(command, shell = True)
    ret.communicate()

def removeAlpha(imageSrc, imageDst):
    # 使用双引号包裹路径，防止文件名空格问题
    command = '{} "{}" -background black -alpha remove "{}"'.format(os_cmd, imageSrc, imageDst)
    if isDebug:
        print(command)
    ret = subprocess.Popen(command, shell = True)
    ret.communicate()

def separateAlphaChannel(imageFileOne, imageFileTwo):
    command = '{} "{}" -channel A -separate "{}"'.format(os_cmd, imageFileOne, imageFileTwo)
    if isDebug:
        print(command)
    ret = subprocess.Popen(command, shell = True)
    ret.communicate()

def zipAlphaChannel(imageSrc, imageDst):
    # cv2 imread 不支持带中文路径，通常需要用 np.fromfile 读取
    # 如果环境是 Linux 通常没问题，Windows 下建议用 imdecode
    # 为了保持原代码风格暂不修改核心读取逻辑，仅做提醒
    srcImage = cv2_imread_safe(imageSrc)
    if srcImage is None:
        return

    shape = srcImage.shape
    
    dstImage = np.zeros((int(shape[0]), int(shape[1])//3, int(shape[2])), np.uint8)
    dstShape = dstImage.shape

    height      = dstShape[0]
    width       = dstShape[1]
    channels    = dstShape[2]

    for row in range(height):
        for col in range(width):
            for channel in range(channels):
                dstImage[row][col][channel] = srcImage[row][col * 3 + channel][0]
    
    cv2_imwrite_safe(imageDst, dstImage)

def zipAlphaChannelPro(imageSrc, imageDst):
    srcImage = cv2_imread_safe(imageSrc)
    if srcImage is None:
        return
    shape = srcImage.shape
    
    dstImage = np.zeros((int(shape[0]), int(shape[1])//3, int(shape[2])), np.uint8)
    dstShape = dstImage.shape

    height      = dstShape[0]
    width       = dstShape[1]
    channels    = dstShape[2]

    for row in range(height):
        for col in range(width):
            for channel in range(channels):
                dstImage[row][col][channel] = srcImage[row][col + channel * width][0]
    cv2_imwrite_safe(imageDst, dstImage)

# --- 辅助函数：解决Windows下OpenCV无法读取中文路径/特殊字符路径的问题 ---
def cv2_imread_safe(file_path):
    try:
        return cv2.imdecode(np.fromfile(file_path, dtype=np.uint8), -1)
    except Exception as e:
        print(f"Error reading image {file_path}: {e}")
        return None

def cv2_imwrite_safe(file_path, img):
    try:
        cv2.imencode('.jpg', img)[1].tofile(file_path)
    except Exception as e:
        print(f"Error writing image {file_path}: {e}")

def appendImageLand(imageFileOne, imageFileTwo, imageFileAppend):
    # 使用双引号包裹路径，防止路径中有空格出错
    command = '{} "{}" "{}" +append "{}"'.format(os_cmd, imageFileTwo, imageFileOne, imageFileAppend)
    
    if isDebug:
        print(command)
    ret = subprocess.Popen(command, shell = True)
    ret.communicate()

def deleteTempFile(filePath):
    if os.path.exists(filePath):
        os.remove(filePath)

def imagesToVideo(imagesPath, videoFile, name_pattern="%05d.jpg"):
    image_sequence_specifier = os.path.join(imagesPath, name_pattern)
    # ffmpeg 的 -i 后面如果包含 %d 这种模式，通常不需要对文件名本身加引号（如果路径没空格），
    # 但为了安全，路径最好不要有空格。
    # 由于我们已经在 temp/output 里强制命名为 00000.jpg，这里基本是安全的。
    command = 'ffmpeg -r {} -i "{}" -vcodec libx264 -pix_fmt yuv420p -b {}k "{}"'.format(fps, image_sequence_specifier, bitrate, videoFile)
    if isDebug:
        print(command)
    ret = subprocess.Popen(command, shell = True)
    ret.communicate()

def updateProgress(progress, total):
    percent = round(progress / total * 100, 2)
    sys.stdout.write('\rprogress : %s [%d/%d]' % (str(percent) + '%', progress, total))
    sys.stdout.flush()

def mkdir(path):
    folder = os.path.exists(path)
    if not folder:
        os.makedirs(path)

if __name__ == '__main__':
    main()

# python convertAlphaVideo-py3.py --dir "path/to/image/dir"