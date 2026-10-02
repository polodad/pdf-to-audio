chrome.runtime.onInstalled.addListener(() => {
    chrome.contextMenus.create({
      id: "read-text",
      title: "Leer texto con IA",
      contexts: ["selection"]
    });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
    if (info.menuItemId === "read-text" && info.selectionText) {
        // Enviar un mensaje al content script para que muestre el reproductor y pida el audio
        chrome.scripting.executeScript({
            target: { tabId: tab.id },
            files: ["content.js"]
        }, () => {
            chrome.tabs.sendMessage(tab.id, {
                action: "play-audio",
                text: info.selectionText
            });
        });
    }
});
