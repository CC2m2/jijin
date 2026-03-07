import axios from "axios";

export const api = axios.create({
  baseURL: "http://127.0.0.1:8000/api/v1",
  timeout: 15000,
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const backendMessage = error?.response?.data?.message;
    const axiosMessage = error?.message;
    const status = error?.response?.status;

    if (backendMessage) {
      return Promise.reject(new Error(backendMessage));
    }

    if (error?.code === "ECONNABORTED") {
      return Promise.reject(new Error("请求超时，服务可能正在拉取外部基金数据，请稍后重试"));
    }

    if (!error?.response) {
      return Promise.reject(new Error(`请求失败，未收到服务响应${axiosMessage ? `: ${axiosMessage}` : ""}`));
    }

    return Promise.reject(new Error(axiosMessage || `请求失败，状态码 ${status ?? "未知"}`));
  }
);
