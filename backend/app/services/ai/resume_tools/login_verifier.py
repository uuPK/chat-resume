# -*- coding: utf-8 -*-
import base64
import time
import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from Crypto.Random import get_random_bytes
import os


# --- 来自 boss-zhipin-login-flow.md 的 fp 生成函数 ---
def generate_fp(i_str, e_b64):
    """
    生成 Boss 直聘登录所需的 fp 设备指纹参数。
    """
    # 1. 准备密钥和明文
    key_bytes = base64.b64decode(e_b64)
    plaintext_bytes = i_str.encode("utf-8")

    # 2. 生成一个16字节的随机IV
    iv_bytes = get_random_bytes(16)

    # 3. 使用AES/CBC模式进行加密 (需要对明文进行PKCS7填充)
    cipher = AES.new(key_bytes, AES.MODE_CBC, iv_bytes)
    padded_plaintext = pad(plaintext_bytes, AES.block_size)
    ciphertext_bytes = cipher.encrypt(padded_plaintext)

    # 4. 组合 IV 和密文
    result_bytes = iv_bytes + ciphertext_bytes

    # 5. 进行Base64编码得到最终的fp值
    fp = base64.b64encode(result_bytes).decode("utf-8")
    return fp


def save_qrcode_image(session, url, qr_id):
    """从URL获取二维码图片并保存到文件"""
    try:
        # 获取二维码图片数据
        resp = session.get(url)
        resp.raise_for_status()

        # 保存二维码图片到当前目录
        filename = f"qrcode_{qr_id}.png"
        with open(filename, "wb") as f:
            f.write(resp.content)

        print(f"✅ 二维码图片已保存为: {filename}")
        print("请使用 Boss 直聘 APP 扫描此图片文件")

        # 尝试在macOS上用预览打开
        if os.name == "posix":  # macOS/Linux
            try:
                os.system(f"open {filename}")
                print("已尝试用系统默认程序打开二维码图片")
            except:
                pass

        return filename

    except Exception as e:
        print(f"❌ 获取或保存二维码失败: {e}")
        print(f"请手动访问以下链接获取二维码: {url}")
        return None


def main():
    """
    执行 Boss 直聘扫码登录流程
    """
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Referer": "https://www.zhipin.com/web/user/?ka=header-login",
            "Origin": "https://www.zhipin.com",
        }
    )

    # 1. 获取登录会话信息
    print("🔑 第一步：获取登录会话信息...")
    randkey_url = "https://www.zhipin.com/wapi/zppassport/captcha/randkey"
    try:
        resp = session.post(randkey_url)
        resp.raise_for_status()
        zp_data = resp.json().get("zpData", {})
        qr_id = zp_data.get("qrId")
        if not qr_id:
            print("❌ 获取 qrId 失败！")
            print(resp.text)
            return
        print(f"✅ 成功获取 qrId: {qr_id}")
    except requests.RequestException as e:
        print(f"❌ 请求失败: {e}")
        return

    # 2. 获取二维码图片
    print("\n📱 第二步：获取二维码图片...")
    qrcode_url = (
        f"https://www.zhipin.com/wapi/zpweixin/qrcode/getqrcode?content={qr_id}"
    )
    qrcode_file = save_qrcode_image(session, qrcode_url, qr_id)

    if not qrcode_file:
        print("❌ 无法获取二维码，登录流程终止")
        return

    # 3. 检查扫码状态（长轮询）
    print("\n⏳ 第三步：等待用户扫码...")
    scan_url = f"https://www.zhipin.com/wapi/zppassport/qrcode/scan?uuid={qr_id}"
    scan_count = 0
    while True:
        try:
            resp = session.get(scan_url, timeout=35)
            if resp.status_code == 200 and resp.json().get("scaned"):
                print("✅ 扫码成功！")
                break
            elif resp.json().get("msg") == "timeout":
                scan_count += 1
                print(f"⏱️ 等待扫码超时，继续轮询... ({scan_count})")
            else:
                scan_count += 1
                print(f"🔄 轮询中... ({scan_count}) - {resp.json()}")
        except requests.exceptions.ReadTimeout:
            scan_count += 1
            print(f"⏱️ 等待扫码超时，继续轮询... ({scan_count})")
            continue
        except requests.RequestException as e:
            print(f"⚠️ 检查扫码状态时出错: {e}")
            time.sleep(2)
        time.sleep(1)

    # 4. 检查登录确认状态（长轮询）
    print("\n👍 第四步：等待用户在手机上确认登录...")
    scan_login_url = (
        f"https://www.zhipin.com/wapi/zppassport/qrcode/scanLogin?qrId={qr_id}"
    )
    confirm_count = 0
    while True:
        try:
            # 这里的 status=1 表示已扫码，等待确认
            resp = session.get(scan_login_url, params={"status": 1}, timeout=35)
            # 如果用户确认，会返回用户信息并设置一些临时cookie
            if resp.status_code == 200:
                print("✅ 用户已确认登录！")
                break
            elif resp.json().get("msg") == "timeout":
                confirm_count += 1
                print(f"⏱️ 等待确认超时，继续轮询... ({confirm_count})")
            else:
                confirm_count += 1
                print(f"🔄 轮询中... ({confirm_count}) - {resp.json()}")

        except requests.exceptions.ReadTimeout:
            confirm_count += 1
            print(f"⏱️ 等待确认超时，继续轮询... ({confirm_count})")
            continue
        except requests.RequestException as e:
            print(f"⚠️ 检查登录确认状态时出错: {e}")
            time.sleep(2)
        time.sleep(1)

    # 5. 获取最终 Cookie
    print("\n🍪 第五步：获取最终 Cookie...")
    # 注意：这里的 i_input 和 E_input 是从文档中获取的示例值
    # 在实际场景中，它们需要从页面JS动态获取，否则此步骤可能会失败
    i_input = "8048b8676fb7d3d8952276e6e98e0bde.f2dc7a63c4b0fbfa4b51a07e2710cf83.fef7e750fc3a1e6327e8a880915aee9c.ae00f848beb1aa591d71d5a80dd3bd95"
    E_input = "clRwXUJBK1VKK0k0IWFbbQ=="
    fp = generate_fp(i_input, E_input)
    print(f"🔧 生成的 fp (每次都不同): {fp}")

    dispatcher_url = f"https://www.zhipin.com/wapi/zppassport/qrcode/dispatcher?qrId={qr_id}&pk=header-login&fp={fp}"
    try:
        # allow_redirects=False 以便观察重定向
        resp = session.get(dispatcher_url, allow_redirects=False)
        print("📤 获取 Cookie 请求已发送...")

        # 成功登录后，服务器会通过 Set-Cookie 头设置最终凭证
        set_cookie_headers = resp.headers.get("Set-Cookie", "")
        if set_cookie_headers:
            print("\n🎉 登录成功！获取到的 Cookie 如下：")
            print("=" * 60)

            # 解析Set-Cookie头
            cookies = {}
            if isinstance(set_cookie_headers, str):
                # 处理单个Set-Cookie头
                cookie_parts = set_cookie_headers.split(",")
                for part in cookie_parts:
                    if "=" in part:
                        name_value = part.strip().split(";")[0].strip()
                        if "=" in name_value:
                            name, value = name_value.split("=", 1)
                            cookies[name.strip()] = value.strip()
            else:
                # 处理多个Set-Cookie头（某些requests版本可能会返回列表）
                for header in set_cookie_headers:
                    if "=" in header:
                        name_value = header.split(";")[0].strip()
                        if "=" in name_value:
                            name, value = name_value.split("=", 1)
                            cookies[name.strip()] = value.strip()

            # 打印所有Cookie
            for name, value in cookies.items():
                print(f"{name}: {value}")
            print("=" * 60)

            # 保存cookie到文件
            with open("cookies.txt", "w") as f:
                for name, value in cookies.items():
                    f.write(f"{name}={value}; ")
            print("📁 Cookie 已保存到 cookies.txt 文件")

        else:
            print("\n❌ 登录失败。")
            print(f"状态码: {resp.status_code}")
            print("响应头:")
            for k, v in resp.headers.items():
                print(f"  {k}: {v}")
            print("响应内容:")
            print(resp.text)
            print("\n💡 失败原因可能是 fp 参数无效，请尝试从浏览器中获取最新的动态值。")

    except requests.RequestException as e:
        print(f"❌ 获取最终 Cookie 时出错: {e}")

    # 清理二维码文件
    if qrcode_file and os.path.exists(qrcode_file):
        try:
            os.remove(qrcode_file)
            print(f"🧹 已清理二维码文件: {qrcode_file}")
        except:
            pass


if __name__ == "__main__":
    # 检查依赖
    try:
        import requests
        from Crypto.Cipher import AES
    except ImportError as e:
        print(f"❌ 缺少必要的库: {e.name}。")
        print("请使用 'pip install requests pycryptodome' 命令安装。")
    else:
        main()

# 全局session管理
_global_session = None


def get_session():
    """获取全局session"""
    global _global_session
    if _global_session is None:
        _global_session = requests.Session()
        _global_session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Referer": "https://www.zhipin.com/web/user/?ka=header-login",
                "Origin": "https://www.zhipin.com",
            }
        )
    return _global_session


def set_cookie(cookie_string: str):
    """设置cookie到全局session"""
    global _global_session
    if _global_session:
        _global_session.headers["Cookie"] = cookie_string


def get_current_cookie() -> str:
    """获取当前cookie"""
    global _global_session
    if _global_session:
        return _global_session.headers.get("Cookie", "")
    return ""


# MCP服务器包装函数
def generate_global_session():
    """为MCP服务器生成全局session"""
    return get_session()


def get_global_session():
    """获取全局session"""
    return get_session()


# 简化的登录步骤函数，供MCP服务器使用
def get_randkey(session):
    """步骤1：获取randkey"""
    randkey_url = "https://www.zhipin.com/wapi/zppassport/captcha/randkey"
    resp = session.post(randkey_url)
    resp.raise_for_status()
    return resp.json()["zpData"]["qrId"]


def get_qrcode(session, qr_id):
    """步骤2：获取二维码图片数据"""
    qr_url = f"https://www.zhipin.com/wapi/zpweixin/qrcode/getqrcode?content={qr_id}"
    resp = session.get(qr_url)
    resp.raise_for_status()
    return resp.content  # 返回图片数据


def check_scan_status(session, qr_id):
    """步骤3：检查扫码状态"""
    scan_url = f"https://www.zhipin.com/wapi/zppassport/qrcode/scan?uuid={qr_id}"
    resp = session.get(scan_url, timeout=35)
    return resp.status_code


def check_login_confirmation(session, qr_id):
    """步骤4：检查登录确认"""
    confirm_url = (
        f"https://www.zhipin.com/wapi/zppassport/qrcode/scanLogin?qrId={qr_id}&status=1"
    )
    resp = session.get(confirm_url, timeout=35)
    return resp.status_code


def get_final_cookie(session, qr_id):
    """步骤5：获取最终cookie"""
    # 构造登录页URL
    login_url = f"https://login.zhipin.com/?ka=header-login&zpwww=1"

    # 需要从之前的响应中获取i_str和e_b64来生成fp
    # 这里使用默认值，实际应用中需要从randkey响应中获取
    i_str = f"{{'platform':'4','bkUa':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36','time':{int(time.time())}}}"
    e_b64 = "L+JXaW9O4A5BjPv6b2Zl6A=="

    # 生成fp参数
    fp = generate_fp(i_str, e_b64)

    # 携带fp参数访问登录页面
    login_with_fp_url = f"{login_url}&fp={fp}"
    resp = session.get(login_with_fp_url)

    # 获取cookie
    cookie_str = ""
    if "set-cookie" in resp.headers:
        cookies = resp.headers["set-cookie"]
        cookie_parts = [c.split(";")[0] for c in cookies.split(", ") if "=" in c]
        cookie_str = "; ".join(cookie_parts)

    # 设置cookie到session
    session.headers["Cookie"] = cookie_str

    # 获取bst参数
    bst_value = ""
    if "bst" in resp.cookies:
        bst_value = resp.cookies["bst"]

    return cookie_str, bst_value
