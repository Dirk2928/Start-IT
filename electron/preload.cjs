const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('api', {
  listGroups: () => ipcRenderer.invoke('groups:list'),
  createGroup: (name) => ipcRenderer.invoke('groups:create', name),
  listLinks: (groupId) => ipcRenderer.invoke('links:list', groupId),
  saveLink: (payload) => ipcRenderer.invoke('links:save', payload),
  deleteLinks: (ids) => ipcRenderer.invoke('links:delete', ids),
  launchSelected: (ids) => ipcRenderer.invoke('links:launch-selected', ids),
  launchVisible: (groupId) => ipcRenderer.invoke('links:launch-visible', groupId),
  getBrowsers: () => ipcRenderer.invoke('app:browsers'),
});
