document.addEventListener('DOMContentLoaded', () => {
    const element = document.querySelector('.menu-bolock');
    document.addEventListener('dblclick', () => {
        if (element.style.display === 'none') {
            element.style.display = 'block';
        } else {
            element.style.display = 'none';
        }
    });
});