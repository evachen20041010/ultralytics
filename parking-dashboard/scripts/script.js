const firebaseConfig = {
  apiKey: "AIzaSyB_6DeMOMFu2r_CQUwldK5Y_0Xdoo7OOpQ",
  authDomain: "parking-test-f9490.firebaseapp.com",
  projectId: "parking-test-f9490",
  storageBucket: "parking-test-f9490.appspot.com",
  messagingSenderId: "409772314042",
  appId: "1:409772314042:web:6f12925484911f322ee183",
  measurementId: "G-ESZT177HTH"
};
  
// Initialize Firebase
const app = firebase.initializeApp(firebaseConfig);
const db = firebase.firestore();
const storage = firebase.storage();