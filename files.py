import os
import time

import common

from driver import get_winDriver

DEFAULT_PATH = 'D:/GitProject/dev/pip/jmcomic/assets/download'
DRIVERS_LIST = get_winDriver()
current_path = ''


def is_image_file(filename):
    # 获取文件名的小写形式并去掉路径
    file_extension = filename.lower().split('.')[-1]

    # 常见图片文件扩展名列表
    image_extensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'webp']

    # 判断文件扩展名是否在图片扩展名列表中
    return file_extension in image_extensions


def check_dir_can_open_jm_view(dirpath):
    return any(f for f in common.files_of_dir(dirpath) if is_image_file(f))


# 获取文件信息的函数
def get_files_data(path):
    """
    获取指定路径下的所有文件、文件夹的信息
    """
    global current_path
    files = []

    try:
        listdir = os.listdir(path)
    except OSError:
        # 无权限
        return []

    for file_name in listdir:
        # 拼接路径
        file_path = os.path.abspath(os.path.join(path, file_name))

        # 判断是文件夹还是文件
        if os.path.isfile(file_path):
            the_type = 'file'
            jm_view = check_dir_can_open_jm_view(common.of_dir_path(file_path))
        else:
            the_type = 'dir'
            jm_view = check_dir_can_open_jm_view(file_path)

        name = file_name
        try:
            size = os.path.getsize(file_path)
        except OSError as e:
            print(e)
            continue

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
            "type": the_type,
            'jm_view': jm_view
        })
    # 更新当前路径
    current_path = path

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
