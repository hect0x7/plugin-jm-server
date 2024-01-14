function openJmView(filename, _fileType) {
    let curPath = getCurPath();
    const viewDir = curPath + '/' + filename

    // console.log(`openJmView -> ${dirPath}`);
    // alert(dirPath)
    const jmViewForm = document.querySelector('#jmViewForm input[type="submit"]');
    const path = document.querySelector('#jmViewForm input[name="path"]');
    const openFromDir = document.querySelector('#jmViewForm input[name="openFromDir"]');
    path.value = viewDir;
    openFromDir.value = curPath;
    jmViewForm.click();
}

function getCurPath() {
    return (document.querySelectorAll('.currentPath span'))[0].innerHTML.trim()
}

function goBack() {
    let curPath = getCurPath();
    let backPath = curPath + '/..';
    console.log(`go back -> ${backPath}`);
    changeDir(backPath)
}


function changeDir(goPath) {
    const pathFormInput = document.querySelector('#pathForm input[type="text"]');
    const SubmitBtn = document.querySelector('#pathForm input[type="submit"]');
    pathFormInput.value = goPath;
    SubmitBtn.click();
}

window.addEventListener('DOMContentLoaded', function () {
    // 两个浮动面板
    const flashTablet = document.querySelector('.flash-tablet');
    const tableHeight = document.querySelector('.files-table').offsetTop;
    const toTopBtn = document.querySelector('#to-top');
    // 点击驱动器标号或点击文件夹触发更新
    const driverLinks = document.querySelectorAll('.drivers-container a');
    const pathFormInput = document.querySelector('#pathForm input[type="text"]');
    const SubmitBtn = document.querySelector('#pathForm input[type="submit"]');
    const dirLinks = document.querySelectorAll('.dir a');


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

    for (let i = 0; i < driverLinks.length; i++) {
        driverLinks[i].addEventListener('click', function (e) {
            e.preventDefault();
            pathFormInput.value = driverLinks[i].getAttribute('location');
            SubmitBtn.click();
        })
    }

    function whenClickDir(e) {
        e.preventDefault();
        let curPath = getCurPath();
        let dir = this.getAttribute('dirname');
        let goPath = curPath + '/' + dir;
        changeDir(goPath);
    }

    for (let i = 0; i < dirLinks.length; i++) {
        dirLinks[i].addEventListener('click', function (e) {
            whenClickDir.call(this, e);
        })
    }

    // 判断当前路径，根目录下“返回上级”按钮要禁用
    const tolastBtns = document.querySelectorAll('.to-lastPath');

    if (getCurPath().length <= 3) {
        for (let i = 0; i < tolastBtns.length; i++) {
            tolastBtns[i].style.cssText = 'background-color: gray;' +
                'background-image: linear-gradient(135deg, rgb(198 207 212) 0%, rgb(172, 173, 195) 100%);' +
                'color: #747474;';
            tolastBtns[i].disabled = 'disabled';
        }
    } else {
    }
})
