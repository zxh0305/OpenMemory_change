import { createSlice, PayloadAction } from '@reduxjs/toolkit';

interface ProfileState {
  userId: string;
  totalMemories: number;
  totalApps: number;
  status: 'idle' | 'loading' | 'succeeded' | 'failed';
  error: string | null;
  apps: any[];
}

// 从 localStorage 读取用户ID，如果不存在则使用默认值
const getInitialUserId = (): string => {
  if (typeof window !== 'undefined') {
    const storedUserId = localStorage.getItem('openmemory_user_id');
    if (storedUserId) {
      return storedUserId;
    }
  }
  return process.env.NEXT_PUBLIC_USER_ID || 'user';
};

const initialState: ProfileState = {
  userId: getInitialUserId(),
  totalMemories: 0,
  totalApps: 0,
  status: 'idle',
  error: null,
  apps: [],
};

const profileSlice = createSlice({
  name: 'profile',
  initialState,
  reducers: {
    setUserId: (state, action: PayloadAction<string>) => {
      state.userId = action.payload;
      // 保存到 localStorage
      if (typeof window !== 'undefined') {
        localStorage.setItem('openmemory_user_id', action.payload);
      }
    },
    setProfileLoading: (state) => {
      state.status = 'loading';
      state.error = null;
    },
    setProfileError: (state, action: PayloadAction<string>) => {
      state.status = 'failed';
      state.error = action.payload;
    },
    resetProfileState: (state) => {
      state.status = 'idle';
      state.error = null;
      const defaultUserId = process.env.NEXT_PUBLIC_USER_ID || 'user';
      state.userId = defaultUserId;
      // 清除 localStorage 中的用户ID
      if (typeof window !== 'undefined') {
        localStorage.removeItem('openmemory_user_id');
      }
    },
    setTotalMemories: (state, action: PayloadAction<number>) => {
      state.totalMemories = action.payload;
    },
    setTotalApps: (state, action: PayloadAction<number>) => {
      state.totalApps = action.payload;
    },
    setApps: (state, action: PayloadAction<any[]>) => {
      state.apps = action.payload;
    }
  },
});

export const {
  setUserId,
  setProfileLoading,
  setProfileError,
  resetProfileState,
  setTotalMemories,
  setTotalApps,
  setApps
} = profileSlice.actions;

export default profileSlice.reducer;