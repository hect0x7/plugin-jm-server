document.addEventListener('DOMContentLoaded', () => {
    // 右侧菜单采用双击显示/隐藏
    const element = document.querySelector('.menu-bolock');
    document.addEventListener('dblclick', () => {
        if (element.style.display === 'none') {
            element.style.display = 'block';
        } else {
            element.style.display = 'none';
        }
    });

    // 跳转到底部
    document.getElementById('gobottom')
        .addEventListener('click', () => {
            window.scrollTo(0, document.body.scrollHeight);
        });

    // 选择页码跳转图片
    document.getElementById('pageselect').addEventListener('change', function () {
        let selectedValue = this.value;
        if (selectedValue !== null) {
            const divid = "page_" + selectedValue;
            let element = document.getElementById(divid);
            if (element) {
                let settop = element.offsetTop - 10 - document.getElementById('Comic_Top_Nav').offsetHeight;
                window.scrollTo(0, settop);
            }
            document.getElementById('pageselect').value = selectedValue;
        }
    });

    window.addEventListener('scroll', function () {
        let wsTop = window.scrollY
        let pageDivs = document.querySelectorAll('div[id*="page_"]');
        let toPage = pageDivs.length - 1;

        for (let div of pageDivs) {
            let divTop = div.offsetTop;
            if (divTop > wsTop) {
                toPage = parseInt(div.getAttribute("data-page"));
                break
            }
        }

        document.getElementById('pageselect').value = toPage;
    });


});