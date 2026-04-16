#!/usr/bin/env python3
"""
统一Azure OpenAI API客户端模块
Unified Azure OpenAI API Client Module

提供统一的GPT-4.1客户端获取和配置，避免重复代码
"""

import base64
import cv2
import numpy as np
# from key_manage import Azure_GPT_4_1_Key
from key_manage import Ali_Cloud_LLM_Key

# 默认配置常量 - Azure OpenAI配置（已注释，现在使用阿里云Qwen）
# DEFAULT_API_VERSION = "2024-12-01-preview"
# DEFAULT_MODEL = "gpt-4.1"
# DEFAULT_AZURE_ENDPOINT = "https://admin-m9uwcx36-eastus2.cognitiveservices.azure.com/"

# 阿里云Qwen兼容OpenAI配置
DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen3.6-plus"


def get_gpt_client():
    """
    获取OpenAI兼容客户端（现在使用阿里云Qwen3.6-plus，原Azure GPT代码已注释）
    :return: OpenAI客户端实例，如果初始化失败返回None
    """
    try:
        # 原Azure OpenAI代码（已注释）
        # from openai import AzureOpenAI
        # client = AzureOpenAI(
        #     api_version=DEFAULT_API_VERSION,
        #     api_key=Azure_GPT_4_1_Key,
        #     azure_endpoint=DEFAULT_AZURE_ENDPOINT
        # )

        # 新阿里云Qwen兼容OpenAI模式
        from openai import OpenAI
        client = OpenAI(
            base_url=DEFAULT_BASE_URL,
            api_key=Ali_Cloud_LLM_Key
        )
        return client
    except ImportError:
        print("警告: 未找到openai模块或key_manage模块，GPT不可用")
        return None
    except Exception as e:
        print(f"警告: GPT客户端初始化失败 ({e})，GPT不可用")
        return None


def encode_image_to_base64(image_path: str) -> str:
    """
    将图片文件编码为base64（用于GPT视觉分析）
    :param image_path: 图片文件路径
    :return: base64编码字符串
    """
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def encode_numpy_image_to_base64(image_array):
    """
    将numpy图像数组编码为base64（用于GPT视觉分析）
    :param image_array: numpy数组格式的图像
    :return: base64编码字符串
    """
    # RGB转BGR（OpenCV格式）
    if len(image_array.shape) == 3 and image_array.shape[2] == 3:
        image_bgr = cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)
    else:
        image_bgr = image_array

    _, buffer = cv2.imencode('.png', image_bgr)
    return base64.b64encode(buffer).decode("utf-8")


# 检查GPT是否可用
def is_gpt_available() -> bool:
    """检查GPT客户端是否可用"""
    return get_gpt_client() is not None
