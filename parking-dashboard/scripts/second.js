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

  const mainRef_first = storage.ref('istockphoto/istockphoto_02/frames');

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
            document.getElementById('main-second').src = url;

            const latestFileName = latestFile.name.replace('.jpg', '');

            for (let i = 1; i <= 4; i++) {
              const relatedImageRef = storage.ref(`istockphoto/istockphoto_02/frames_four/${latestFileName}_${i}.jpg`);
              relatedImageRef.getDownloadURL().then((relatedUrl) => {
                document.getElementById(`small-second-${i}`).src = relatedUrl;
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

  const docRef = db.collection('istockphoto').doc('istockphoto_02');

  docRef.get().then((doc) => {
    if (doc.exists) {
      const data = doc.data();
      const max_empty_space = parseInt(data.max_empty_space);
      const min_empty_space = parseInt(data.min_empty_space);

      if (data && data.total_space !== undefined) {
        document.getElementById('main-second-text').textContent = `車位總數：${data.total_space}　空車位總數：${data.empty_space || '未提供'}`;
      } else {
        console.error('No data found or total_space not defined');
      }

      if (data.max_empty_space !== undefined && data.min_empty_space !== undefined){
        document.getElementById(`small-second-${max_empty_space}-text`).textContent = "空車位較多";
        document.getElementById(`small-second-${max_empty_space}-text`).style.backgroundColor = 'green';
        document.getElementById(`small-second-${max_empty_space}-text`).style.color = 'white';
        document.getElementById(`small-second-${min_empty_space}-text`).textContent = "空車位較少";
        document.getElementById(`small-second-${min_empty_space}-text`).style.backgroundColor = 'red';
        document.getElementById(`small-second-${min_empty_space}-text`).style.color = 'white';
      } else {
        console.error('No data found or max_empty_space or min_empty_space not defined');
      }
    } else {
      console.error('No such document!');
    }
  }).catch((error) => {
    console.error('Error getting document:', error);
  });
});
  