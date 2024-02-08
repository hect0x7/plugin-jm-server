from urllib.parse import quote
import os
import time

import common


class FileManager:
    def __init__(self, default_path, current_path):
        self.default_path = default_path
        self.current_path = current_path

    @property
    def DRIVERS_LIST(self):
        # 判断如果是windows系统
        if os.name == 'nt':
            from .driver import get_winDriver
            return get_winDriver()
        else:
            return ['/']

    def get_jm_view_images(self, path):
        images_data = []

        give_up_sort = False

        for f in self.files_of_dir_safe(path):
            if not self.is_image_file(f):
                continue
            f = quote(f)
            name = common.of_file_name(f)
            try:
                index = int(name[:name.index('.')])
            except ValueError:
                give_up_sort = True
                index = None

            images_data.append({
                'filename': name,
                'data_original': f'/view_file?path={f}',
                'index': index,
            })

        if give_up_sort is False:
            images_data.sort(key=lambda item: item['index'])

        return images_data

    @staticmethod
    def is_image_file(filename):
        file_extension = filename.lower().split('.')[-1]
        image_extensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'webp']
        return file_extension in image_extensions

    @staticmethod
    def files_of_dir_safe(dir_path):
        try:
            return common.files_of_dir(dir_path)
        except OSError:
            return []

    def check_dir_can_open_jm_view(self, dirpath):
        return any(f for f in self.files_of_dir_safe(dirpath) if self.is_image_file(f))

    def get_files_data(self, path):
        files = []

        for file_path in self.files_of_dir_safe(path):

            if os.path.isfile(file_path):
                the_type = 'file'
                jm_view = self.check_dir_can_open_jm_view(common.of_dir_path(file_path))
            else:
                the_type = 'dir'
                jm_view = self.check_dir_can_open_jm_view(file_path)

            name = common.of_file_name(file_path)
            try:
                size = os.path.getsize(file_path)
            except OSError:
                continue

            size = self.file_size_format(size, the_type)

            try:
                getctime = os.path.getctime(file_path)
                ctime = time.localtime(getctime)
                time_str = time.strftime("%Y-%m-%d %H:%M:%S", ctime)
            except OSError:
                continue

            files.append({
                "name": name,
                "size": size,
                "ctime": time_str,
                "type": the_type,
                'jm_view': jm_view
            })
        self.current_path = path

        files.sort(key=lambda it: it['ctime'], reverse=True)
        return files

    @staticmethod
    def file_size_format(size, the_type):
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

    def get_current_path(self):
        return self.current_path
