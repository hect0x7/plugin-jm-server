import os
import time

from driver import get_winDriver

DEFAULT_PATH = 'D:/GitProject/dev/pip/jmcomic/assets/download'
DRIVERS_LIST = get_winDriver()
current_path = ''


# 获取文件信息的函数
def get_files_data(path):
    """
    获取指定路径下的所有文件、文件夹的信息
    """
    global current_path
    files = []

    for the_name in os.listdir(path):
        # 拼接路径
        file_path = path + "/" + the_name

        # 判断是文件夹还是文件
        if os.path.isfile(file_path):
            the_type = 'file'
        else:
            the_type = 'dir'

        name = the_name
        size = os.path.getsize(file_path)
        size = file_size_format(size, the_type)
        # 创建时间
        getctime = os.path.getctime(file_path)
        try:
            ctime = time.localtime(getctime)
            # 封装成字典形式追加给 files 列表
            time_str = "{}/{}/{}".format(ctime.tm_year, ctime.tm_mon, ctime.tm_mday)
        except OSError as e:
            print(e)
            continue

        files.append({
            "name": name,
            "size": size,
            # 拼接年月日信息
            "ctime": time_str,
            "type": the_type
        })
    # 更新当前路径
    current_path = path

    print('files_data:\n'
          f'{files}')

    return files


def file_size_format(size, the_type):
    """
    文件大小格式化，携带单位
    """
    if the_type == 'dir':
        return '<DIR>'
    else:
        if size < 1024:
            return '%i' % size + ' B'
        elif 1024 < size <= 1048576:
            return '%.1f' % float(size / 1024) + ' KB'
        elif 1048576 < size <= 1073741824:
            return '%.1f' % float(size / 1048576) + ' MB'
        elif 1073741824 < size <= 1099511627776:
            return '%.1f' % float(size / 1073741824) + ' GB'


def get_current_path():
    return current_path


if __name__ == '__main__':
    text = get_files_data('E:/')
