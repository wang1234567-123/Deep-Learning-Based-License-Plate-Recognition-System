import platform
import uuid
import hashlib


def get_machine_id() -> str:
    """生成机器码。

    根据当前系统信息（平台、架构、MAC地址）生成唯一机器码，
    使用 SHA256 取前16位并转大写，前缀为 HERTZ_STUDIO_。
    """
    system_info = f"{platform.platform()}-{platform.machine()}-{uuid.getnode()}"
    return 'HERTZ_STUDIO_' + hashlib.sha256(system_info.encode()).hexdigest()[:16].upper()


if __name__ == "__main__":
    machine_code = get_machine_id()
    print(f"您的机器码是: {machine_code}")