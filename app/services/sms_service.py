import logging

logger = logging.getLogger(__name__)


def send_sms_code(phone: str, code: str) -> bool:
    """
    模拟发送短信验证码：将验证码打印到控制台，方便开发时查看。
    """
    logger.info("=" * 50)
    logger.info(f"[DEV SMS] 验证码发送至 {phone}")
    logger.info(f"[DEV SMS] 验证码: {code}")
    logger.info("=" * 50)
    return True
