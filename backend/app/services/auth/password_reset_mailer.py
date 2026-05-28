"""用于发送密码重置邮件。"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import Protocol

from app.infra.config import Settings, settings

logger = logging.getLogger(__name__)


class PasswordResetMailer(Protocol):
    """用于约束密码重置邮件发送器接口。"""

    def send_password_reset(self, *, email: str, reset_link: str) -> None:
        """用于发送包含密码重置链接的邮件。"""


class SettingsPasswordResetMailer:
    """用于按运行时配置发送或记录密码重置链接。"""

    def __init__(self, config: Settings = settings):
        """用于保存邮件发送所需配置。"""
        self.config = config

    def send_password_reset(self, *, email: str, reset_link: str) -> None:
        """用于发送密码重置邮件，未配置SMTP时写入日志。"""
        if not self.config.PASSWORD_RESET_SMTP_HOST.strip():
            logger.info("password reset link issued email=%s link=%s", email, reset_link)
            return
        message = self._build_message(email=email, reset_link=reset_link)
        self._send_message(message)

    def _build_message(self, *, email: str, reset_link: str) -> EmailMessage:
        """用于构造密码重置邮件正文。"""
        message = EmailMessage()
        message["Subject"] = "Reset your OfferMaster password"
        message["From"] = self.config.PASSWORD_RESET_EMAIL_FROM
        message["To"] = email
        message.set_content(
            "Use this link to reset your OfferMaster password. "
            f"The link expires in {self.config.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} minutes.\n\n"
            f"{reset_link}"
        )
        return message

    def _send_message(self, message: EmailMessage) -> None:
        """用于通过SMTP发送已构造好的邮件。"""
        with smtplib.SMTP(
            self.config.PASSWORD_RESET_SMTP_HOST,
            self.config.PASSWORD_RESET_SMTP_PORT,
            timeout=10,
        ) as smtp:
            if self.config.PASSWORD_RESET_SMTP_TLS:
                smtp.starttls()
            if self.config.PASSWORD_RESET_SMTP_USERNAME:
                smtp.login(
                    self.config.PASSWORD_RESET_SMTP_USERNAME,
                    self.config.PASSWORD_RESET_SMTP_PASSWORD,
                )
            smtp.send_message(message)
