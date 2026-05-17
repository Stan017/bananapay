module.exports = {
  openURL:   jest.fn(async () => {}),
  canOpenURL: jest.fn(async () => true),
  createURL:  jest.fn((path) => `bananapay://${path}`),
};
