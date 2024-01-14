# plugin-jm-server

想法起源：https://github.com/hect0x7/JMComic-Crawler-Python/issues/192

基于原项目：https://github.com/AiCorein/Flask-Files-Server

为了方便修改，将原项目中的文件复制到本项目中，然后进行修改



# 使用方式



## 1. pip安装

```shell
pip install plugin_jm_server
```



## 2. 运行代码

* **HTTP版**

```python
from plugin_jm_server import *

# http
server = JmServer(
    'D:/',
    'password',
)
server.run(
    host='0.0.0.0',
    port=80,
)
```

* **HTTPS版**

```python
from plugin_jm_server import *

# https
server = JmServer(
    'D:/',
    'password',
)
server.run(
    host='0.0.0.0',
    port=443,
    ssl_context='adhoc',
)
```



# 效果图（文件浏览、整章看图）

## 1. 电脑浏览器访问
![](images/3.png)
![](images/4.png)
![](images/5.png)

## 2. 手机浏览器访问
![](images/1.jpeg)
![](images/2.jpeg)
![](images/7.jpeg)

