/*
Websocket Section
 */

let ws = new WebSocket('ws://' + location.host + '/gamedata-collect');

ws.onopen = function() {
  console.log('Connected.');
};

var count = 0;

ws.onmessage = function(evt) {
  if(count == 60) {
    data = JSON.parse(evt.data);
    var str = JSON.stringify(data, null, 2); // spacing level = 2
    document.getElementById("disp-json").innerHTML = str;
    console.log(str);
    count = 0;
  }
  count++;
};

ws.onclose = function() {
 console.log('Disconnected');
};
