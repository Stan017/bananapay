// Mock de axios — cada test puede sobreescribir con mockResolvedValue / mockRejectedValue
const mockAxiosInstance = {
  get:          jest.fn(),
  post:         jest.fn(),
  put:          jest.fn(),
  patch:        jest.fn(),
  delete:       jest.fn(),
  interceptors: {
    request:  { use: jest.fn(), eject: jest.fn() },
    response: { use: jest.fn(), eject: jest.fn() },
  },
};

const axios = {
  create:       jest.fn(() => mockAxiosInstance),
  get:          jest.fn(),
  post:         jest.fn(),
  put:          jest.fn(),
  patch:        jest.fn(),
  delete:       jest.fn(),
  interceptors: {
    request:  { use: jest.fn(), eject: jest.fn() },
    response: { use: jest.fn(), eject: jest.fn() },
  },
};

module.exports = axios;
module.exports.default = axios;
module.exports.__mockInstance = mockAxiosInstance;
