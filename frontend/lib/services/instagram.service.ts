import apiClient from '../api';

export interface InstagramConnectRequest {
  influencer_id: string;
  code: string;
  redirect_uri: string;
}

export interface InstagramAccountInfo {
  instagram_id: string;
  username: string;
  account_type: string;
  media_count: number;
  is_business_account: boolean;
}

export interface InstagramConnectResponse {
  success: boolean;
  message: string;
  account_info: InstagramAccountInfo;
}

export interface InstagramStatus {
  is_connected: boolean;
  instagram_username?: string;
  account_type?: string;
  connected_at?: string;
  is_active: boolean;
}

export class InstagramService {
  static async connectAccount(
    data: InstagramConnectRequest
  ): Promise<InstagramConnectResponse> {
    const { influencer_id, ...requestData } = data;
    return await apiClient.post<InstagramConnectResponse>(
      `/api/v1/influencers/${influencer_id}/instagram/connect`,
      requestData
    );
  }

  static async disconnectAccount(influencerId: string): Promise<void> {
    await apiClient.delete(`/api/v1/influencers/${influencerId}/instagram/disconnect`);
  }

  static async getStatus(influencerId: string): Promise<InstagramStatus> {
    return await apiClient.get<InstagramStatus>(
      `/api/v1/influencers/${influencerId}/instagram/status`
    );
  }

  static async verifyConnection(influencerId: string): Promise<{ is_valid: boolean; message: string }> {
    return await apiClient.post(`/api/v1/instagram/verify/${influencerId}`);
  }
}
