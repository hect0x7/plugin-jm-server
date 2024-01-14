from urllib.parse import quote
import os
import re
from typing import Optional

import common
from flask import Flask, abort
from flask import render_template, send_from_directory
from flask import request, session, redirect, flash

from .files import FileManager


# noinspection PyMethodMayBeStatic
class JmServer:
    DEFAULT_PORT = 80
    # 匹配移动端设备的正则表达式
    MATCH_EXP = 'Android|webOS|iPhone|iPad|iPod|BlackBerry'

    def __init__(self,
                 default_path,
                 password,
                 current_path=None,
                 img_overwrite: Optional[dict] = None,
                 **extra,
                 ):
        """
        创建一个共享文件服务器

        :param default_path: 默认路径
        :param password: 登录密码
        :param current_path: 当前路径
        :param extra: 额外配置
        """
        if current_path is None:
            current_path = default_path

        # 自定义背景图片，采用覆盖文件的方式
        self.handle_img_overwrite(img_overwrite or {})

        # 创建项目以及初始化一些关键信息
        self.app = Flask(__name__,
                         template_folder='templates',
                         static_folder='static',
                         static_url_path='/static',
                         )
        self.app.secret_key = __file__
        # 设置登录密钥
        self.password = password
        self.file_manager = FileManager(default_path, current_path)
        self.extra = extra

    def verify(self):
        """
        验证登录状态
        """
        if session.get('password', None) == self.password:
            return True
        else:
            return False

    def mobile_check(self):
        """
        设备类型检查
        """
        try:
            if session.mobile == 'yes':
                return True
            elif session.mobile == 'no':
                return False
        except AttributeError:
            if re.search(self.MATCH_EXP, request.headers.get('User-Agent')):
                session.mobile = 'yes'
                return True
            else:
                session.mobile = 'no'
                return False

    def url_format(self, device_isMobile, default_load_url):
        """
        根据设备类型返回对应的资源 url
        """
        if device_isMobile:
            return './m_' + default_load_url
        else:
            return default_load_url

    def url_random_arg(self):
        """
        url添加一个随机参数，防止浏览器缓存
        """
        # from random import randint
        # return randint(100000, 1000000)
        return 0

    def jm_view(self):
        """
        以禁漫章节的模式观看指定文件夹下的图片
        """
        if not self.verify():
            return redirect('/login')

        # path是要阅读的文件夹
        path = request.args.get('path', None)
        # 从哪个文件夹打开的
        openFromDir = request.args.get('openFromDir', self.file_manager.get_current_path())

        if path is None:
            return redirect('/')

        path = os.path.abspath(path)
        if os.path.isfile(path):
            path = common.of_dir_path(path)

        # 文件不存在
        if common.file_not_exists(path):
            return abort(404)

        print(f'jm_view: {path}')
        return render_template(self.url_format(self.mobile_check(), "jm_view.html"),
                               data={
                                   'title': common.of_file_name(path),
                                   'images': self.file_manager.get_jm_view_images(path),
                                   'openFromDir': quote(openFromDir),
                               },
                               randomArg=self.url_random_arg())

    def view_file(self):
        """
        获取单个文件
        """
        # 判断是否已经在登录状态上
        if not self.verify():
            # 之前没有登录过,返回登录页
            return redirect('/login')

        # 已经登录了，返回文件夹内文件信息（此时为默认路径）
        path = request.args.get('path', None)
        if path is None:
            return abort(403)

        return send_from_directory(os.path.dirname(path),
                                   os.path.basename(path),
                                   )

    def index(self):
        """
        共享文件主页
        """
        # 判断是否已经在登录状态上
        if not self.verify():
            # 之前没有登录过,返回登录页
            return redirect('/login')

        # 已经登录了，返回文件夹内文件信息（此时为默认路径）
        path = request.args.get('path', self.file_manager.default_path)
        path = os.path.abspath(path)
        path = common.fix_filepath(path)

        # 文件不存在
        if common.file_not_exists(path):
            return abort(404)

        return render_template(self.url_format(self.mobile_check(), "index.html"),
                               data={
                                   "files": self.file_manager.get_files_data(path),
                                   "drivers": self.file_manager.DRIVERS_LIST,
                                   "currentPath": path,
                               },
                               randomArg=self.url_random_arg())

    def login(self):
        """
        登录页
        """
        device_isMobile = self.mobile_check()
        if request.method == 'GET':
            if self.verify():
                return redirect('/')
            else:
                # 之前没有登录过,返回一个登录页
                return render_template(self.url_format(device_isMobile, 'login.html'),
                                       randomArg=self.url_random_arg())
        else:
            # 先保存才能验证
            password = request.form.get('password')
            session['password'] = password
            if self.verify():
                # 重定向到首页
                return redirect('/')
            else:
                # 登录失败的情况
                flash("密码错误！")
                return redirect('/login')

    def logout(self):
        """
        注销
        """
        if self.verify():
            # 声明重定向对象
            resp = redirect('/')
            # 删除值
            resp.delete_cookie('password')
            session.pop('password', None)
            return resp
        else:
            # 没有登录过,返回登录页
            return redirect('/login')

    def file_content(self, filename):
        """
        下载文件
        """
        if self.verify():
            # 若文件存在
            if filename in os.listdir(self.file_manager.get_current_path()):
                # 发送文件 参数：路径，文件名
                return send_from_directory(self.file_manager.get_current_path(), filename)
            else:
                # 否则返回错误页面
                device_isMobile = self.mobile_check()
                return render_template(self.url_format(device_isMobile, "download_error.html"),
                                       filename=filename,
                                       randomArg=self.url_random_arg())
        else:
            return redirect('/login')

    def upload(self):
        """
        上传文件
        """
        if self.verify():
            if request.method == "POST":
                # 获取文件 拼接存储路径并保存
                upload_file = request.files['file']
                upload_file.save(os.path.join(self.file_manager.get_current_path(), upload_file.filename))

                # 返回上传成功的消息给前端
                return '提示：上传的%s已经存储到了服务器中!' % upload_file.filename

            # 如果是 GET 方法：
            device_isMobile = self.mobile_check()
            return render_template(self.url_format(device_isMobile, "upload.html"),
                                   randomArg=self.url_random_arg())
        else:
            return redirect('/login')

    def run(self, **kwargs):
        kwargs.setdefault('port', self.DEFAULT_PORT)
        # 添加路由
        self.app.add_url_rule('/jm_view', 'jm_view', self.jm_view, methods=['GET'])
        self.app.add_url_rule("/view_file/", 'view_file', self.view_file, methods=['GET'], strict_slashes=False)
        self.app.add_url_rule('/', 'index', self.index, methods=['GET'])
        self.app.add_url_rule('/login', 'login', self.login, methods=['GET', 'POST'])
        self.app.add_url_rule('/logout', 'logout', self.logout, methods=['GET', 'POST'])
        self.app.add_url_rule("/download_file/<filename>", 'file_content', self.file_content)
        self.app.add_url_rule("/upload_file", 'upload', self.upload, methods=['GET', 'POST'])

        # 监听在所有 IP 地址上
        self.app.run(**kwargs)

    def handle_img_overwrite(self, img_overwrite: dict):
        bg_dir = os.path.abspath(__file__ + '/../static/img/')
        for orig_filename, overwrite_filepath in img_overwrite.items():
            orig_filepath = os.path.join(bg_dir, orig_filename)

            # copy overwrite_filepath to orig_filepath
            if os.path.exists(overwrite_filepath):
                with open(overwrite_filepath, 'rb') as f:
                    with open(orig_filepath, 'wb') as f2:
                        f2.write(f.read())
                        print(f'overwrite img [{orig_filename}] -> [{overwrite_filepath}]')
