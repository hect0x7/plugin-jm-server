import os


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
            if '[WinError 21]' in str(e):
                del driver_list[i]
            # 异常类型不为 “设备未就绪” 的再次抛出异常供调试
            else:
                raise (PermissionError, e)
        finally:
            num -= 1

    # 返回列表
    return driver_list


if __name__ == "__main__":
    paths = get_winDriver()
    print(paths)
