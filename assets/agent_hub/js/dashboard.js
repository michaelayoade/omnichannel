document.addEventListener('DOMContentLoaded', function() {
    const statusLog = document.getElementById('status-log');
    const notificationLog = document.getElementById('notification-log');

    function logMessage(element, message) {
        const p = document.createElement('p');
        p.textContent = message;
        element.appendChild(p);
        element.scrollTop = element.scrollHeight;
    }

    // Connect to AgentStatusConsumer
    const statusSocket = new WebSocket(
        'ws://' + window.location.host + '/ws/agent/status/'
    );

    statusSocket.onopen = function(e) {
        logMessage(statusLog, 'Status connection established.');
    };

    statusSocket.onmessage = function(e) {
        const data = JSON.parse(e.data);
        logMessage(statusLog, `Agent ${data.agent_id} is now ${data.status}.`);
    };

    statusSocket.onclose = function(e) {
        console.error('Status socket closed unexpectedly');
        logMessage(statusLog, 'Status connection closed.');
    };

    // Connect to NotificationConsumer
    const notificationSocket = new WebSocket(
        'ws://' + window.location.host + '/ws/agent/notifications/'
    );

    notificationSocket.onopen = function(e) {
        logMessage(notificationLog, 'Notification connection established.');
    };

    notificationSocket.onmessage = function(e) {
        const data = JSON.parse(e.data);
        logMessage(notificationLog, `Notification (${data.type}): ${JSON.stringify(data.payload)}`);
    };

    notificationSocket.onclose = function(e) {
        console.error('Notification socket closed unexpectedly');
        logMessage(notificationLog, 'Notification connection closed.');
    };
});
