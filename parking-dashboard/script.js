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

    document.getElementById('parkingLot1').addEventListener('click', function() {
        window.location.href = 'main.html';
    });

    document.getElementById('parkingLot2').addEventListener('click', function() {
        window.location.href = 'second.html';
    });
});
