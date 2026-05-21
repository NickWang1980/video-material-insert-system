import argparse
import gc
import json
import os
import sys

os.environ["GRADIO_SERVER_NAME"] = "0.0.0.0"
import subprocess
import threading
import time
import traceback
import uuid
from enum import Enum
import queue
import shutil
from functools import partial
from datetime import datetime, timedelta

import cv2
import gradio as gr
from flask import Flask, request
import uuid

import service.trans_dh_service
from h_utils.custom import CustomError
from y_utils.config import GlobalConfig
from y_utils.logger import logger
import scipy.io.wavfile as wav

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULT_PATH=os.path.join(BASE_DIR, "result")
AUDIO_PATH=os.path.join(BASE_DIR, "audio")

# 确保必要文件夹存在
os.makedirs(AUDIO_PATH, exist_ok=True)
os.makedirs(RESULT_PATH, exist_ok=True)

# 全局变量存储任务日志和状态
task_logs = []
task_start_time = None

def write_video_gradio(
        output_imgs_queue,
        temp_dir,
        result_dir,
        work_id,
        audio_path,
        result_queue,
        width,
        height,
        fps,
        watermark_switch=0,
        digital_auth=0,
        temp_queue=None,
):
    output_mp4 = os.path.join(temp_dir, "{}-t.mp4".format(work_id))
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    result_path = os.path.join(result_dir, "{}-r.mp4".format(work_id))
    video_write = cv2.VideoWriter(output_mp4, fourcc, fps, (width, height))
    print("Custom VideoWriter init done")
    try:
        while True:
            state, reason, value_ = output_imgs_queue.get()
            if type(state) == bool and state == True:
                logger.info(
                    "Custom VideoWriter [{}]视频帧队列处理已结束".format(work_id)
                )
                logger.info(
                    "Custom VideoWriter Silence Video saved in {}".format(
                        os.path.realpath(output_mp4)
                    )
                )
                video_write.release()
                break
            else:
                if type(state) == bool and state == False:
                    logger.error(
                        "Custom VideoWriter [{}]任务视频帧队列 -> 异常原因:[{}]".format(
                            work_id, reason
                        )
                    )
                    raise CustomError(reason)
                for result_img in value_:
                    video_write.write(result_img)
        if video_write is not None:
            video_write.release()
        if watermark_switch == 1 and digital_auth == 1:
            logger.info(
                "Custom VideoWriter [{}]任务需要水印和数字人标识".format(work_id)
            )
            if width > height:
                command = 'ffmpeg -y -i {} -i {} -i {} -i {} -filter_complex "overlay=(main_w-overlay_w)-10:(main_h-overlay_h)-10,overlay=(main_w-overlay_w)-10:10" -c:a aac -crf 15 -strict -2 {}'.format(
                    audio_path,
                    output_mp4,
                    GlobalConfig.instance().watermark_path,
                    GlobalConfig.instance().digital_auth_path,
                    result_path,
                )
                logger.info("command:{}".format(command))
            else:
                command = 'ffmpeg -y -i {} -i {} -i {} -i {} -filter_complex "overlay=(main_w-overlay_w)-10:(main_h-overlay_h)-10,overlay=(main_w-overlay_w)-10:10" -c:a aac -crf 15 -strict -2 {}'.format(
                    audio_path,
                    output_mp4,
                    GlobalConfig.instance().watermark_path,
                    GlobalConfig.instance().digital_auth_path,
                    result_path,
                )
                logger.info("command:{}".format(command))
        elif watermark_switch == 1 and digital_auth == 0:
            logger.info("Custom VideoWriter [{}]任务需要水印".format(work_id))
            command = 'ffmpeg -y -i {} -i {} -i {} -filter_complex "overlay=(main_w-overlay_w)-10:(main_h-overlay_h)-10" -c:a aac -crf 15 -strict -2 {}'.format(
                audio_path,
                output_mp4,
                GlobalConfig.instance().watermark_path,
                result_path,
            )
            logger.info("command:{}".format(command))
        elif watermark_switch == 0 and digital_auth == 1:
            logger.info("Custom VideoWriter [{}]任务需要数字人标识".format(work_id))
            if width > height:
                command = 'ffmpeg -loglevel warning -y -i {} -i {} -i {} -filter_complex "overlay=(main_w-overlay_w)-10:10" -c:a aac -crf 15 -strict -2 {}'.format(
                    audio_path,
                    output_mp4,
                    GlobalConfig.instance().digital_auth_path,
                    result_path,
                )
                logger.info("command:{}".format(command))
            else:
                command = 'ffmpeg -loglevel warning -y -i {} -i {} -i {} -filter_complex "overlay=(main_w-overlay_w)-10:10" -c:a aac -crf 15 -strict -2 {}'.format(
                    audio_path,
                    output_mp4,
                    GlobalConfig.instance().digital_auth_path,
                    result_path,
                )
                logger.info("command:{}".format(command))
        else:
            command = "ffmpeg -loglevel warning -y -i {} -i {} -c:a aac -c:v libx264 -crf 15 -strict -2 {}".format(
                audio_path, output_mp4, result_path
            )
            logger.info("Custom command:{}".format(command))
        subprocess.call(command, shell=True)
        print("###### Custom Video Writer write over")
        print(f"###### Video result saved in {os.path.realpath(result_path)}")
        result_queue.put([True, result_path])
    except Exception as e:
        logger.error(
            "Custom VideoWriter [{}]视频帧队列处理异常结束，异常原因:[{}]".format(
                work_id, e.__str__()
            )
        )
        result_queue.put(
            [
                False,
                "[{}]视频帧队列处理异常结束，异常原因:[{}]".format(
                    work_id, e.__str__()
                ),
            ]
        )
    logger.info("Custom VideoWriter 后处理进程结束")


service.trans_dh_service.write_video = write_video_gradio


def convert_audio_to_16k(input_file, output_file):
    """
    将MP3文件转换为单声道16kHz 16bit PCM WAV格式
    参数：
    input_file (str): 输入文件路径（如：hzt.mp3）
    output_file (str): 输出文件路径（如：mono_16k.wav）
    """
    try:
        # 构建FFmpeg命令
        command = [
            'ffmpeg',
            '-y',  # 覆盖已存在文件（可选）
            '-i', input_file,
            '-acodec', 'pcm_s16le',  # 16位PCM编码
            output_file
        ]

        # 执行命令
        result = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        print("转换成功！")
        print("FFmpeg输出：")
        print(result.stderr)

    except FileNotFoundError:
        print("错误：未找到FFmpeg，请先安装FFmpeg并添加到系统环境变量")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"转换失败，错误码：{e.returncode}")
        print("错误信息：")
        print(e.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"发生未知错误：{str(e)}")
        sys.exit(1)


def get_video_info(video_file):
    """获取视频分辨率信息"""
    if video_file is None:
        return "请先上传视频"
    try:
        cap = cv2.VideoCapture(video_file)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps if fps > 0 else 0
        cap.release()
        
        info = f"分辨率: {width}x{height}\n帧率: {fps:.2f} fps\n时长: {duration:.2f} 秒\n帧数: {frame_count}"
        return info
    except Exception as e:
        return f"获取视频信息失败: {str(e)}"


def add_log(message):
    """添加日志消息"""
    global task_logs
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    task_logs.append(f"[{timestamp}] {message}")
    return "\n".join(task_logs)


def clear_logs():
    """清除日志"""
    global task_logs
    task_logs = []
    return ""


class VideoProcessor:
    def __init__(self):
        self.task = service.trans_dh_service.TransDhTask()
        self.basedir = GlobalConfig.instance().result_dir
        self.is_initialized = False
        self._initialize_service()
        print("VideoProcessor init done")

    def _initialize_service(self):
        logger.info("开始初始化 trans_dh_service...")
        try:
            time.sleep(5)
            logger.info("trans_dh_service 初始化完成。")
            self.is_initialized = True
        except Exception as e:
            logger.error(f"初始化 trans_dh_service 失败: {e}")

    def process_video(
            self, audio_file, video_file
    ):
        global task_start_time, task_logs
        
        # 重置日志
        task_logs = []
        task_start_time = time.time()
        
        # 步骤1: 初始化检查
        yield add_log("任务开始初始化..."), None
        
        while not self.is_initialized:
            yield add_log("服务尚未完成初始化，等待 1 秒..."), None
            time.sleep(1)
        
        work_id = str(uuid.uuid1())
        code = work_id
        final_video = None
        
        try:
            # 步骤2: 任务开始
            yield add_log(f"任务ID: {code}"), None
            
            # 获取视频信息
            cap = cv2.VideoCapture(video_file)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = frame_count / fps if fps > 0 else 0
            cap.release()
            
            yield add_log(f"视频信息: {width}x{height}, {fps:.2f}fps, 时长{duration:.2f}秒"), None
            
            # 预估时间用于进度计算
            estimated_seconds = duration * 1.5 + 30
            
            # 步骤3: 保存音频
            print(audio_file)
            print(video_file)
            audio_file_name = uuid.uuid4()
            audio_file_full_path = os.path.join(AUDIO_PATH,f'{audio_file_name}.wav')
            wav.write(audio_file_full_path, audio_file[0], audio_file[1])
            print("audio_file_full_path>>>>>>>", audio_file_full_path)
            
            yield add_log("正在转换音频格式..."), None
            
            audio_file_full_path_16k = os.path.join(AUDIO_PATH,f'{audio_file_name}_16k.wav')
            convert_audio_to_16k(audio_file_full_path, audio_file_full_path_16k)

            audio_path = audio_file_full_path_16k
            video_path = video_file

            yield add_log("正在初始化数字人任务..."), None
            
            self.task.task_dic[code] = ""
            
            # 步骤4: 启动后台任务
            task_result = {
                'completed': False,
                'success': False,
                'result_path': None,
                'error': None
            }
            
            def run_task():
                try:
                    self.task.work(audio_path, video_path, code, 0, 0, 0, 1)
                    task_result['result_path'] = self.task.task_dic[code][2]
                    task_result['success'] = True
                except Exception as e:
                    task_result['error'] = str(e)
                    logger.error(f"任务执行错误: {e}")
                finally:
                    task_result['completed'] = True
            
            task_thread = threading.Thread(target=run_task)
            task_thread.start()
            
            yield add_log("数字人任务开始执行..."), None
            
            # 步骤5: 等待并显示进度
            stages = [
                (0.15, "正在进行音频特征提取..."),
                (0.35, "正在进行人脸检测和对齐..."),
                (0.55, "正在生成数字人面部..."),
                (0.75, "正在合成视频帧..."),
                (0.90, "正在进行视频后处理..."),
            ]
            
            start_time = time.time()
            stage_index = 0
            
            # 先yield一次确保UI开始更新
            current_log = "\n".join(task_logs)
            yield current_log, None
            
            while not task_result['completed'] or stage_index < len(stages):
                elapsed = time.time() - start_time
                
                # 更新日志阶段
                if stage_index < len(stages):
                    expected_time = (stage_index + 1) * (estimated_seconds / len(stages))
                    if elapsed >= expected_time:
                        p, desc = stages[stage_index]
                        yield add_log(desc), None
                        stage_index += 1
                    else:
                        # 定期yield保持UI更新，但不添加新日志
                        current_log = "\n".join(task_logs)
                        yield current_log, None
                else:
                    # 所有阶段都显示完了，等待任务完成
                    if not task_result['completed']:
                        current_log = "\n".join(task_logs)
                        yield current_log, None
                
                # 检查是否可以结束
                if task_result['completed'] and stage_index >= len(stages):
                    break
                
                time.sleep(0.5)
            
            # 等待线程真的结束
            while task_thread.is_alive():
                time.sleep(0.3)
                current_log = "\n".join(task_logs)
                yield current_log, None
            
            # 步骤6: 处理结果
            if task_result['success']:
                result_path = task_result['result_path']
                print(f"result_path>>>>>>>>>>>{result_path}")
                
                final_video = None
                if result_path and os.path.exists(result_path):
                    if os.path.isfile(result_path):
                        final_video = result_path
                    elif os.path.isdir(result_path):
                        for f in os.listdir(result_path):
                            if f.endswith(('.mp4', '.avi', '.mov', '.mkv')):
                                final_video = os.path.join(result_path, f)
                                break
                
                if final_video and os.path.isfile(final_video):
                    elapsed_time = time.time() - task_start_time
                    yield add_log(f"任务完成！耗时: {elapsed_time:.2f} 秒"), final_video
                else:
                    yield add_log("错误: 未找到生成的视频文件"), None
            else:
                error_msg = task_result['error'] or "未知错误"
                yield add_log(f"任务执行失败: {error_msg}"), None

        except Exception as e:
            logger.error(f"处理视频时发生错误: {e}")
            yield add_log(f"错误: {str(e)}"), None
            raise gr.Error(str(e))


if __name__ == "__main__":
    
    processor = VideoProcessor()
    
    with gr.Blocks(title="八爪鱼数字人系统") as demo:
        gr.Markdown("# 🎬 八爪鱼数字人系统V2.0")
        gr.Markdown("上传音频和视频文件，即可生成数字人视频,支持20-50系英伟达显卡，最低8G显存可玩")
        
        with gr.Row():
            with gr.Column(scale=1):
                audio_input = gr.Audio(
                    label="上传音频文件(要干净的人声)",
                    type="numpy"
                )
                video_input = gr.Video(
                    label="上传视频文件，视频中必须含有一个人的正脸",
                    height=400
                )
                video_info = gr.Textbox(
                    label="视频信息",
                    placeholder="上传视频后将显示分辨率信息",
                    lines=4,
                    interactive=False
                )
                
                with gr.Row():
                    submit_btn = gr.Button("开始生成", variant="primary", size="lg")
                    clear_btn = gr.Button("清除日志", size="lg")
            
            with gr.Column(scale=1):
                task_log = gr.Textbox(
                    label="任务日志",
                    placeholder="任务日志将在这里显示",
                    lines=10,
                    interactive=False
                )
                video_output = gr.Video(
                    label="生成的视频",
                    height=450
                )
        
        # 视频上传后自动获取信息
        video_input.change(
            fn=get_video_info,
            inputs=video_input,
            outputs=video_info
        )
        
        # 提交按钮点击事件
        submit_btn.click(
            fn=processor.process_video,
            inputs=[audio_input, video_input],
            outputs=[task_log, video_output],
            show_progress="hidden"
        )
        
        # 清除日志按钮
        clear_btn.click(
            fn=clear_logs,
            outputs=task_log
        )
    
    demo.queue().launch(inbrowser=True)
