"""
Boss直聘登录和职位工具核心逻辑
"""

from __future__ import annotations

import base64
import json
import threading
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Optional

import requests
import os

try:
    from Crypto.Cipher import AES
    from Crypto.Random import get_random_bytes
    from Crypto.Util.Padding import pad
except ImportError:  # pragma: no cover - 环境缺少依赖时使用降级算法
    AES = None
    get_random_bytes = None
    pad = None


@dataclass
class LoginStatus:
    """登录状态数据模型"""

    is_logged_in: bool = False
    cookie: Optional[str] = None
    bst: Optional[str] = None
    qr_id: Optional[str] = None
    login_step: str = "idle"
    image_path: Optional[str] = None
    image_base64: Optional[str] = None
    error_message: Optional[str] = None


class BossZhipinState:
    """Boss直聘全局状态管理"""

    def __init__(self) -> None:
        self.login_status = LoginStatus()
        self.session: Optional[requests.Session] = None
        self.qr_dir = Path(__file__).resolve().parent / "qr_codes"
        self.qr_dir.mkdir(exist_ok=True)
        self._lock = threading.Lock()

    def get_session(self) -> requests.Session:
        """获取或创建HTTP会话"""
        if self.session is None:
            self.session = requests.Session()
            self.session.headers.update(
                {
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Referer": "https://www.zhipin.com/web/user/?ka=header-login",
                    "Origin": "https://www.zhipin.com",
                }
            )
        return self.session

    def update_login_status(self, **kwargs: Any) -> None:
        """线程安全地更新登录状态"""
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self.login_status, key):
                    setattr(self.login_status, key, value)

    def reset_login(self) -> None:
        """重置登录状态与会话"""
        with self._lock:
            self.login_status = LoginStatus()
            if self.session:
                self.session.cookies.clear()

    def save_qrcode(self, qr_id: str, data: bytes) -> str:
        """保存二维码图片并返回路径"""
        file_path = self.qr_dir / f"qrcode_{qr_id}.png"
        with open(file_path, "wb") as f:
            f.write(data)
        return str(file_path)


state = BossZhipinState()


class BossZhipinAPI:
    """Boss直聘API操作集合"""

    EXPERIENCE_MAP = {
        "在校生": 108,
        "应届生": 102,
        "不限": 101,
        "一年以内": 103,
        "一到三年": 104,
        "三到五年": 105,
        "五到十年": 106,
        "十年以上": 107,
    }

    JOB_TYPE_MAP = {
        "全职": 1901,
        "兼职": 1903,
    }

    SALARY_MAP = {
        "3k以下": 402,
        "3-5k": 403,
        "5-10k": 404,
        "10-20k": 405,
        "20-50k": 406,
        "50以上": 407,
    }

    @staticmethod
    def generate_fp(i_str: str, e_b64: str) -> str:
        """生成设备指纹参数"""
        if AES is None or pad is None or get_random_bytes is None:
            # 降级方案：使用随机字节模拟fp
            return base64.b64encode(os.urandom(32)).decode("utf-8")

        key_bytes = base64.b64decode(e_b64)
        plaintext_bytes = i_str.encode("utf-8")
        iv_bytes = get_random_bytes(16)

        cipher = AES.new(key_bytes, AES.MODE_CBC, iv_bytes)
        padded_plaintext = pad(plaintext_bytes, AES.block_size)
        ciphertext_bytes = cipher.encrypt(padded_plaintext)

        result_bytes = iv_bytes + ciphertext_bytes
        return base64.b64encode(result_bytes).decode("utf-8")

    @staticmethod
    def get_randkey(session: requests.Session) -> str:
        url = "https://www.zhipin.com/wapi/zppassport/captcha/randkey"
        resp = session.post(url)
        resp.raise_for_status()
        return resp.json()["zpData"]["qrId"]

    @staticmethod
    def get_qrcode(session: requests.Session, qr_id: str) -> bytes:
        url = f"https://www.zhipin.com/wapi/zpweixin/qrcode/getqrcode?content={qr_id}"
        resp = session.get(url)
        resp.raise_for_status()
        return resp.content

    @staticmethod
    def get_final_cookie(session: requests.Session, qr_id: str) -> tuple[str, str]:
        i_str = "8048b8676fb7d3d8952276e6e98e0bde.f2dc7a63c4b0fbfa4b51a07e2710cf83.fef7e750fc3a1e6327e8a880915aee9c.ae00f848beb1aa591d71d5a80dd3bd95"
        e_b64 = "clRwXUJBK1VKK0k0IWFbbQ=="
        fp = BossZhipinAPI.generate_fp(i_str, e_b64)
        dispatcher_url = f"https://www.zhipin.com/wapi/zppassport/qrcode/dispatcher?qrId={qr_id}&pk=header-login&fp={fp}"
        resp = session.get(dispatcher_url, allow_redirects=False)

        set_cookie_headers = resp.headers.get("Set-Cookie", "")
        cookies: Dict[str, str] = {}
        if isinstance(set_cookie_headers, str):
            parts = set_cookie_headers.split(",")
        else:
            parts = set_cookie_headers or []

        for part in parts:
            if "=" in part:
                name_value = part.strip().split(";", 1)[0]
                if "=" in name_value:
                    name, value = name_value.split("=", 1)
                    cookies[name.strip()] = value.strip()

        cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
        bst_value = cookies.get("bst", "")

        if cookie_str:
            session.headers["Cookie"] = cookie_str

        return cookie_str, bst_value

    @staticmethod
    def setup_api_headers(session: requests.Session, cookie: str, bst: str) -> None:
        session.headers.update(
            {
                "Cookie": cookie,
                "zp_token": bst,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Referer": "https://www.zhipin.com/web/user/?ka=header-login",
                "Origin": "https://www.zhipin.com",
            }
        )

    @staticmethod
    def get_job_list(session: requests.Session, params: Dict[str, Any]) -> Dict[str, Any]:
        url = "https://www.zhipin.com/wapi/zpgeek/pc/recommend/job/list.json"

        converted = {
            "experience": BossZhipinAPI.EXPERIENCE_MAP.get(params.get("experience", "不限"), 101),
            "jobType": BossZhipinAPI.JOB_TYPE_MAP.get(params.get("jobType", "全职"), 1901),
            "salary": BossZhipinAPI.SALARY_MAP.get(params.get("salary", "不限"), 0),
        }

        query = {
            "page": params.get("page", 1),
            "pageSize": params.get("pageSize", 15),
            "_": int(time.time() * 1000),
            **converted,
        }

        resp = session.get(url, params=query, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise ValueError(data.get("message", "未知错误"))

        zp_data = data.get("zpData", {})
        job_list = zp_data.get("jobList", [])
        return {
            "status": "success",
            "data": {
                "total": len(job_list),
                "hasMore": zp_data.get("hasMore", False),
                "jobList": job_list,
            },
        }

    @staticmethod
    def greet_boss(session: requests.Session, security_id: str, job_id: str) -> Dict[str, Any]:
        url = "https://www.zhipin.com/wapi/zpgeek/friend/add.json"
        params = {"securityId": security_id, "jobId": job_id}
        resp = session.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise ValueError(data.get("message", "发送失败"))
        return {"status": "success", "message": "打招呼发送成功", "data": data.get("zpData", {})}


def _monitor_login(qr_id: str) -> None:
    """后台线程，监控扫码和确认状态"""
    session = state.get_session()
    scan_url = f"https://www.zhipin.com/wapi/zppassport/qrcode/scan?uuid={qr_id}"
    confirm_url = f"https://www.zhipin.com/wapi/zppassport/qrcode/scanLogin?qrId={qr_id}&status=1"

    try:
        while True:
            if state.login_status.login_step == "logged_in":
                return

            resp = session.get(scan_url, timeout=35)
            data = resp.json()
            if data.get("scaned"):
                state.update_login_status(login_step="scanned")
                break
            time.sleep(2)

        while True:
            resp = session.get(confirm_url, timeout=35)
            if resp.status_code == 200:
                state.update_login_status(login_step="confirmed")
                cookie_str, bst_value = BossZhipinAPI.get_final_cookie(session, qr_id)
                if cookie_str:
                    state.update_login_status(
                        is_logged_in=True,
                        cookie=cookie_str,
                        bst=bst_value,
                        login_step="logged_in",
                    )
                return
            time.sleep(2)
    except Exception as exc:
        state.update_login_status(error_message=str(exc))
    finally:
        pass


def start_login(auto_mode: bool = True) -> Dict[str, Any]:
    """启动登录流程"""
    state.reset_login()
    session = state.get_session()
    try:
        qr_id = BossZhipinAPI.get_randkey(session)
        qr_bytes = BossZhipinAPI.get_qrcode(session, qr_id)
        image_base64 = base64.b64encode(qr_bytes).decode("utf-8")
        image_path = state.save_qrcode(qr_id, qr_bytes)
        state.update_login_status(
            qr_id=qr_id,
            login_step="qr_generated",
            image_path=image_path,
            image_base64=image_base64,
        )

        thread = threading.Thread(target=_monitor_login, args=(qr_id,), daemon=True)
        thread.start()

        return {
            "status": "qr_generated",
            "message": "二维码已生成，请扫码完成登录",
            "qr_id": qr_id,
            "image_path": image_path,
            "image_base64": image_base64,
            "login_step": "qr_generated",
            "mode": "auto" if auto_mode else "interactive",
        }
    except Exception as exc:
        state.update_login_status(error_message=str(exc))
        return {"status": "error", "message": f"登录流程启动失败: {exc}"}


def get_login_status() -> Dict[str, Any]:
    """返回当前登录状态"""
    return asdict(state.login_status)


def fetch_jobs(params: Dict[str, Any]) -> Dict[str, Any]:
    """获取推荐职位"""
    if not state.login_status.is_logged_in or not state.login_status.cookie:
        return {"status": "error", "message": "请先完成登录"}

    session = state.get_session()
    BossZhipinAPI.setup_api_headers(session, state.login_status.cookie, state.login_status.bst or "")
    try:
        return BossZhipinAPI.get_job_list(session, params)
    except Exception as exc:
        return {"status": "error", "message": f"获取职位失败: {exc}"}


def send_greeting_request(security_id: str, job_id: str) -> Dict[str, Any]:
    """发送打招呼"""
    if not state.login_status.is_logged_in or not state.login_status.cookie:
        return {"status": "error", "message": "请先完成登录"}

    session = state.get_session()
    BossZhipinAPI.setup_api_headers(session, state.login_status.cookie, state.login_status.bst or "")
    try:
        return BossZhipinAPI.greet_boss(session, security_id, job_id)
    except Exception as exc:
        return {"status": "error", "message": f"发送打招呼失败: {exc}"}
