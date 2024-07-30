document.addEventListener('DOMContentLoaded', function() {
    const menuButton = document.getElementById('menuButton');
    const sidebar = document.getElementById('sidebar');

    menuButton.addEventListener('click', function() {
        sidebar.classList.toggle('active');
        menuButton.classList.toggle('active');
        if (menuButton.textContent === '☰') {
            menuButton.textContent = '✖'; // 变成叉叉
        } else {
            menuButton.textContent = '☰'; // 变回menu icon
        }
    });

    document.getElementById('main-page').addEventListener('click', function() {
        window.location.href = '/parking-dashboard/main.html';
    });

    document.getElementById('first-parking').addEventListener('click', function() {
        window.location.href = '/parking-dashboard/page/first.html';
    });

    document.getElementById('second-parking').addEventListener('click', function() {
        window.location.href = '/parking-dashboard/page/second.html';
    });
});
