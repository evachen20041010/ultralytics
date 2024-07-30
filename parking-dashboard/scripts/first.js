document.addEventListener('DOMContentLoaded', function() {
  const menuButton = document.getElementById('menuButton');
  const sidebar = document.getElementById('sidebar');

  menuButton.addEventListener('click', function() {
    sidebar.classList.toggle('active');
    menuButton.classList.toggle('active');
    if (menuButton.textContent === '☰') {
       menuButton.textContent = '✖';
    } else {
      menuButton.textContent = '☰';
    }
  });

  document.getElementById('main-page').addEventListener('click', function() {
    window.location.href = '/parking-dashboard/main.html';
  });

  document.getElementById('first-parking').addEventListener('click', function() {
    window.location.href = '/parking-dashboard/pages/first.html';
  });

  document.getElementById('second-parking').addEventListener('click', function() {
    window.location.href = '/parking-dashboard/pages/second.html';
  });

  // Fetch and display image from Firebase Storage
  const mainRef_first = storage.ref('istockphoto/istockphoto_01/frames');

  mainRef_first.listAll().then((res) => {
    let latestFile = null;
    let latestFileTime = 0;

    res.items.forEach((itemRef) => {
      itemRef.getMetadata().then((metadata) => {
        const creationTime = new Date(metadata.timeCreated).getTime();
        if (creationTime > latestFileTime) {
          latestFileTime = creationTime;
          latestFile = itemRef;
        }

        if (latestFile) {
          latestFile.getDownloadURL().then((url) => {
            document.getElementById('main-first').src = url;

            const latestFileName = latestFile.name.replace('.jpg', '');

            for (let i = 1; i <= 4; i++) {
              const relatedImageRef = storage.ref(`istockphoto/istockphoto_01/frames_four/${latestFileName}_${i}.jpg`);
              relatedImageRef.getDownloadURL().then((relatedUrl) => {
                document.getElementById(`small-first-${i}`).src = relatedUrl;
              }).catch((error) => {
                console.error(`Error getting related image ${i} URL:`, error);
              });
            }
          }).catch((error) => {
            console.error("Error getting parking image URL:", error);
          });
        }
      }).catch((error) => {
        console.error("Error getting metadata:", error);
      });
    });
  }).catch((error) => {
    console.error("Error listing files:", error);
  });
});
  