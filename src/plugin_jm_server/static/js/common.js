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
    let goBottom = document.getElementById('gobottom');
    if (goBottom != null) {
        goBottom
            .addEventListener('click', () => {
                window.scrollTo(0, document.body.scrollHeight);
            });
    }

    // 选择页码跳转图片
    let pageSelect = document.getElementById('pageselect');
    if (pageSelect != null) {
        pageSelect.addEventListener('change', function () {
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
    }


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

    const lazyImages = document.querySelectorAll(".lazyload");

    const observer = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;
                img.src = img.getAttribute("data-src");
                img.classList.remove("lazyload");
                observer.unobserve(img);
            }
        });
    });

    lazyImages.forEach(img => {
        observer.observe(img);
    });
    document.getElementById("loadAll").addEventListener('click', function () {
        lazyImages.forEach(img => {
            img.src = img.getAttribute("data-src");
            img.classList.remove("lazyload");
        });
    })

});