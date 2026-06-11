import { api } from './client'

export const setPortfolioVisibility = (public_: boolean) =>
  api.post<{ public: boolean; portfolio_url: string | null }>('/api/v1/portfolio/visibility', { public: public_ })
