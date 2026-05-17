const mockRouter = {
  push:    jest.fn(),
  replace: jest.fn(),
  back:    jest.fn(),
  canGoBack: jest.fn(() => true),
};

module.exports = {
  useRouter:   jest.fn(() => mockRouter),
  useLocalSearchParams: jest.fn(() => ({})),
  useSegments: jest.fn(() => []),
  Link:        ({ children }) => children,
  router:      mockRouter,
};
