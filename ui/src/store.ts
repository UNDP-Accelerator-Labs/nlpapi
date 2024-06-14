import { configureStore } from '@reduxjs/toolkit';
import searchStateSliceReducer from './search/SearchStateSlice';

const store = configureStore({
  reducer: {
    searchState: searchStateSliceReducer,
  },
});

export default store;

export type RootState = ReturnType<typeof store.getState>;
// FIXME for reference
// ts-unused-exports:disable-next-line
export type AppDispatch = typeof store.dispatch;
