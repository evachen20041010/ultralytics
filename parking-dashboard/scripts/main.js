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

  document.getElementById('details-button-1').addEventListener('click', function() {
    window.location.href = '/parking-dashboard/pages/first.html';
  });

  document.getElementById('details-button-2').addEventListener('click', function() {
    window.location.href = '/parking-dashboard/pages/second.html';
  });

  for (let i = 1; i <= 2; i++){
    const mainRef_first = storage.ref(`istockphoto/istockphoto_0${i}/frames`);
    const docRef = db.collection('istockphoto').doc(`istockphoto_0${i}`);

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
              document.getElementById(`img-${i}`).src = url;
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

    docRef.get().then((doc) => {
      if (doc.exists) {
        const data = doc.data();
  
        if (data && data.total_space !== undefined) {
          document.getElementById(`img-text-${i}`).textContent = `車位總數：${data.total_space}　空車位總數：${data.empty_space || '未提供'}`;
        } else {
          console.error('No data found or total_space not defined');
        }
      } else {
        console.error('No such document!');
      }
    }).catch((error) => {
      console.error('Error getting document:', error);
    });
  }
});
  