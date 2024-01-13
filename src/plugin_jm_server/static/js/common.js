document.addEventListener('DOMContentLoaded', () => {
    const element = document.querySelector('.menu-bolock');
    document.addEventListener('dblclick', () => {
        if (element.style.display === 'none') {
            element.style.display = 'block';
        } else {
            element.style.display = 'none';
        }
    });

//     id=gobottom，对这个元素实现跳转到页面最底部
    const bottom = document.getElementById('gobottom');
    bottom.addEventListener('click', () => {
        window.scrollTo(0, document.body.scrollHeight);
    });
});