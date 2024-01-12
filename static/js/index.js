window.addEventListener('DOMContentLoaded', function () {
    // 两个浮动面板
    const flashTablet = document.querySelector('.flash-tablet');
    const tableHeight = document.querySelector('.files-table').offsetTop;
    const toTopBtn = document.querySelector('#to-top');

    window.addEventListener('scroll', function () {
        if (window.pageYOffset > tableHeight) {
            flashTablet.style.display = 'block';
        } else {
            flashTablet.style.display = 'none';
        }
    })

    toTopBtn.addEventListener('click', function () {
        window.scrollTo({
            top: 0,
            behavior: 'smooth',
        })
    })

    // 点击驱动器标号或点击文件夹触发更新
    const driverLinks = document.querySelectorAll('.drivers-container a');
    const pathFormInput = document.querySelector('#pathForm input[type="text"]');
    const SubmitBtn = document.querySelector('#pathForm input[type="submit"]');

    for (let i = 0; i < driverLinks.length; i++) {
        driverLinks[i].addEventListener('click', function (e) {
            e.preventDefault();
            pathFormInput.value = driverLinks[i].getAttribute('location');
            SubmitBtn.click();
        })
    }

    const dirLinks = document.querySelectorAll('.dir a');
    const curPathNode = document.querySelectorAll('.currentPath span');


    function whenClickDir(e) {
        e.preventDefault();
        let curPath = curPathNode[0].innerHTML;
        let dir = this.getAttribute('dirname');
        let toPath = curPath + '/' + dir;
        pathFormInput.value = toPath;
        SubmitBtn.click();
    }

    for (let i = 0; i < dirLinks.length; i++) {
        dirLinks[i].addEventListener('click', function (e) {
            whenClickDir.call(this, e);
        })
    }

    // 判断当前路径，根目录下“返回上级”按钮要禁用
    const tolastBtns = document.querySelectorAll('.to-lastPath');

    if (curPathNode[0].innerHTML.length <= 3) {
        for (let i = 0; i < tolastBtns.length; i++) {
            tolastBtns[i].style.cssText = 'background-color: gray;' +
                'background-image: linear-gradient(135deg, rgb(198 207 212) 0%, rgb(172, 173, 195) 100%);' +
                'color: #747474;';
            tolastBtns[i].disabled = 'disabled';
        }
    } else {
    }
})
