import os
import re
from random import randint

import common
from flask import Flask, abort
from flask import render_template, send_from_directory
from flask import request, session, redirect, flash

from files import get_files_data, DEFAULT_PATH, DRIVERS_LIST, \
    get_current_path, get_jm_view_images

# 创建项目以及初始化一些关键信息
app = Flask(__name__,
            template_folder='templates',
            static_folder='static',
            static_url_path='/static',
            )
# 这里是预先将值存储在系统环境变量中了
app.secret_key = '123'
# 匹配移动端设备的正则表达式
MATCH_EXP = 'Android|webOS|iPhone|iPad|iPod|BlackBerry'
# 设置登录用户名和密码
SPECIFY_SECRET = ''


def verify():
    """
    验证登录状态
    """
    if session.get('uname', None) == SPECIFY_SECRET:
        return True
    else:
        return False


def mobile_check():
    """
    设备类型检查
    """
    try:
        if session.mobile == 'yes':
            return True
        elif session.mobile == 'no':
            return False
    except AttributeError:
        if re.search(MATCH_EXP, request.headers.get('User-Agent')):
            session.mobile = 'yes'
            return True
        else:
            session.mobile = 'no'
            return False


def url_format(device_isMobile, default_load_url):
    """
    根据设备类型返回对应的资源 url
    """
    if device_isMobile:
        return './h5/m_' + default_load_url
    else:
        return default_load_url


def url_random_arg():
    """
    url添加一个随机参数，防止浏览器缓存
    """
    return randint(100000, 1000000)


@app.route('/jm_view', methods=['GET'])
def jm_view():
    """
    以禁漫章节的模式观看指定文件夹下的图片
    """
    if not verify():
        return redirect('/login')

    # path是要阅读的文件夹
    path = request.args.get('path', None)
    # 从哪个文件夹打开的
    openFromDir = request.args.get('openFromDir', get_current_path())

    if path is None:
        return redirect('/')

    if os.path.isfile(path):
        path = common.of_dir_path(path)

    # 文件不存在
    if common.file_not_exists(path):
        return abort(404)

    print(f'jm_view: {path}')
    return render_template(url_format(mobile_check(), "jm_view.html"),
                           data={
                               'title': common.of_file_name(path),
                               'images': get_jm_view_images(path),
                               'openFromDir': openFromDir,
                           },
                           randomArg=url_random_arg())


@app.route("/view_file/", methods=['GET'])
def view_file():
    """
    获取单个文件
    """
    # 判断是否已经在登录状态上
    if not verify():
        # 之前没有登录过,返回登录页
        return redirect('/login')

    # 已经登录了，返回文件夹内文件信息（此时为默认路径）
    path = request.args.get('path', None)
    if path is None:
        return abort(403)

    return send_from_directory(os.path.dirname(path),
                               os.path.basename(path),
                               )


@app.route('/', methods=['GET'])
def index():
    """
    共享文件主页
    """
    # 判断是否已经在登录状态上
    if not verify():
        # 之前没有登录过,返回登录页
        return redirect('/login')

    # 已经登录了，返回文件夹内文件信息（此时为默认路径）
    path = request.args.get('path', DEFAULT_PATH)
    path = os.path.abspath(path)

    # 文件不存在
    if common.file_not_exists(path):
        return abort(404)

    return render_template(url_format(mobile_check(), "index.html"),
                           data={
                               "files": get_files_data(path),
                               "drivers": DRIVERS_LIST,
                               "currentPath": path,
                           },
                           randomArg=url_random_arg())


@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    登录页
    """
    device_isMobile = mobile_check()
    if request.method == 'GET':
        if verify():
            return redirect('/')
        else:
            # 之前没有登录过,返回一个登录页
            return render_template(url_format(device_isMobile, 'login.html'),
                                   randomArg=url_random_arg())
    else:
        # 先保存才能验证
        uname = request.form.get('uname')
        session['uname'] = uname
        if verify():
            # 重定向到首页
            return redirect('/')
        else:
            # 登录失败的情况
            flash("该用户名和密码不存在，请重试")
            return redirect('/login')


@app.route('/logout', methods=['GET', 'POST'])
def logout():
    """
    注销
    """
    if verify():
        # 声明重定向对象
        resp = redirect('/')
        # 删除值
        resp.delete_cookie('uname')
        session.pop('uname', None)
        return resp
    else:
        # 没有登录过,返回登录页
        return redirect('/login')


@app.route("/download_file/<filename>")
def file_content(filename):
    """
    下载文件
    """
    if verify():
        # 若文件存在
        if filename in os.listdir(get_current_path()):
            # 发送文件 参数：路径，文件名
            return send_from_directory(get_current_path(), filename)
        else:
            # 否则返回错误页面
            device_isMobile = mobile_check()
            return render_template(url_format(device_isMobile, "download_error.html"),
                                   filename=filename,
                                   randomArg=url_random_arg())
    else:
        return redirect('/login')


@app.route("/upload_file", methods=['GET', 'POST'])
def upload():
    """
    上传文件
    """
    if verify():
        if request.method == "POST":
            # 获取文件 拼接存储路径并保存
            upload_file = request.files['file']
            upload_file.save(os.path.join(get_current_path(), upload_file.filename))

            # 返回上传成功的消息给前端
            return '提示：上传的%s已经存储到了服务器中!' % upload_file.filename

        # 如果是 GET 方法：
        device_isMobile = mobile_check()
        return render_template(url_format(device_isMobile, "upload.html"),
                               randomArg=url_random_arg())
    else:
        return redirect('/login')


if __name__ == '__main__':
    # 监听在所有 IP 地址上
    app.run(host='0.0.0.0', port=5000, debug=True)
