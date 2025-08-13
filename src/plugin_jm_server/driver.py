import os
import re


def get_winDriver():
    """
    Windows操作系统下,返回全部驱动器卷标['C:\','D:\']
    """
    import psutil
    # 返回驱动器卷标列表
    driver_list = sorted([driver.device for driver in psutil.disk_partitions(True)])

    i = 0
    num = len(driver_list)
    while num != 0:
        # 重新格式化分隔符
        driver_name = driver_list[i]
        driver_name = driver_name.strip('\\')
        driver_name += '/'

        # 测试各驱动器是否可访问，目的是筛除未就绪驱动器，如空光驱
        try:
            os.listdir(driver_name)
            driver_list[i] = driver_name
            i += 1
        except PermissionError as e:
            del driver_list[i]
            mobj = re.match(r'\[WinError (\d+)\]', str(e))
            # ERROR_NOT_READY, ERROR_ACCESS_DENIED
            if mobj is not None and mobj.group(1) not in {'21', '5'}:
                print(f'Drive {driver_name} unexpectedly unavailable: {e}')
        finally:
            num -= 1

    # 返回列表
    return driver_list


if __name__ == "__main__":
    paths = get_winDriver()
    print(paths)
