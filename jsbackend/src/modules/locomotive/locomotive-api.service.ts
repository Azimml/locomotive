import { Injectable, Logger } from "@nestjs/common";
import { ConfigService } from "@nestjs/config";
import axios, { AxiosInstance } from "axios";

export interface Locomotive {
  locomotive_id: number;
  locomotive_full_name: string;
  locomotive_type: string;
  location_id: number;
  location_name: string;
  organization_id: number;
  organization_name: string;
  state: string;
  repair_counts_by_year?: Record<
    string,
    {
      counts: Record<string, number>;
      total: number;
    }
  >;
  inspection_details?: Record<string, string>;
}

export interface LocomotiveModel {
  id: number;
  name: string;
  locomotive_type: string;
  locomotive_count: number;
}

export interface StateCount {
  state: string;
  count: number;
}

export interface Stats {
  total_locomotives: number;
  total_models: number;
  state_counts: StateCount[];
}

export interface LocomotiveTypeCount {
  locomotive_type: string;
  locomotive_count: number;
}

export interface ActiveRepair {
  locomotive_id: number;
  locomotive_name: string;
  locomotive_state: string;
  repair_type_name: string;
  repair_type_name_ru: string | null;
  repair_type_name_uz: string | null;
}

export interface LastRepair {
  locomotive_id: number;
  locomotive_name: string;
  repair_type_name: string | null;
  repair_type_name_ru: string | null;
  repair_type_name_uz: string | null;
  last_updated_at: string | null;
}

export interface LocomotiveInfo {
  locomotive_id: number;
  locomotive_full_name: string;
  locomotive_type: string;
  location_id: number;
  location_name: string;
  organization_id: number;
  organization_name: string;
  state: string;
  repair_counts_by_year: Record<
    string,
    {
      counts: Record<string, number>;
      total: number;
    }
  >;
  inspection_details: Record<string, string>;
}

export interface InspectionCount {
  inspection_type_id: number;
  name: string;
  name_ru: string;
  name_uz: string;
  locomotive_count: number;
}

export interface DepoInfo {
  depo_id: number;
  depo_name: string;
  locomotive_count: number;
  locomotive_type_counts: Record<string, number>;
  state_counts: Record<string, number>;
}

export interface RepairStatsByYear {
  year: number;
  repair_type_counts: Record<string, number>;
  total_locomotives: number;
}

@Injectable()
export class LocomotiveApiService {
  private readonly logger = new Logger(LocomotiveApiService.name);
  private readonly httpClient: AxiosInstance;

  private readonly stateTranslations: Record<string, string[]> = {
    in_use: ["foydalanishda", "ekspluatatsiyada", "ishda", "liniyada"],
    in_inspection: ["tamirda", "remontda", "tekshiruvda"],
    in_reserve: ["rezervda", "bekor", "zahirada"],
  };

  constructor(private readonly configService: ConfigService) {
    this.httpClient = axios.create({
      baseURL: this.configService.get<string>("LOCOMOTIVE_API_URL"),
      timeout: 30000,
      headers: {
        Accept: "application/json",
      },
    });
  }

  async getLocomotives(): Promise<Locomotive[]> {
    try {
      const response = await this.httpClient.get<Locomotive[]>("/locomotives");
      return response.data;
    } catch (error) {
      this.logger.error("Lokomotivlarni olishda xatolik", error);
      throw error;
    }
  }

  async getLocomotiveModels(): Promise<LocomotiveModel[]> {
    try {
      const response =
        await this.httpClient.get<LocomotiveModel[]>("/locomotive-models");
      return response.data;
    } catch (error) {
      this.logger.error("Lokomotiv modellarini olishda xatolik", error);
      throw error;
    }
  }

  async getStats(): Promise<Stats> {
    try {
      const response = await this.httpClient.get<Stats>("/stats");
      return response.data;
    } catch (error) {
      this.logger.error("Statistikani olishda xatolik", error);
      throw error;
    }
  }

  async getLocomotiveTypes(): Promise<LocomotiveTypeCount[]> {
    try {
      const response =
        await this.httpClient.get<LocomotiveTypeCount[]>("/locomotive-types");
      return response.data;
    } catch (error) {
      this.logger.error("Lokomotiv turlarini olishda xatolik", error);
      throw error;
    }
  }

  async getActiveRepairs(): Promise<ActiveRepair[]> {
    try {
      const response =
        await this.httpClient.get<ActiveRepair[]>("/repairs/active");
      return response.data;
    } catch (error) {
      this.logger.error("Faol ta'mirlarni olishda xatolik", error);
      throw error;
    }
  }

  async getAllLastRepairs(): Promise<LastRepair[]> {
    try {
      const response =
        await this.httpClient.get<LastRepair[]>("/repairs/last-all");
      return response.data;
    } catch (error) {
      this.logger.error("Oxirgi ta'mirlarni olishda xatolik", error);
      throw error;
    }
  }

  async getLastRepair(
    locomotiveId?: number,
    locomotiveName?: string,
  ): Promise<LastRepair | null> {
    try {
      const params: Record<string, any> = {};
      if (locomotiveId) params.locomotive_id = locomotiveId;
      if (locomotiveName) params.locomotive_name = locomotiveName;

      const response = await this.httpClient.get<LastRepair>("/repairs/last", {
        params,
      });
      return response.data;
    } catch (error) {
      this.logger.error("Oxirgi ta'mirni olishda xatolik", error);
      return null;
    }
  }

  async getLocomotiveInfo(
    locomotiveName: string,
  ): Promise<LocomotiveInfo | null> {
    try {
      const response = await this.httpClient.get<LocomotiveInfo>(
        "/locomotive-info",
        { params: { locomotive_name: locomotiveName } },
      );
      return response.data;
    } catch (error) {
      this.logger.error("Lokomotiv ma'lumotlarini olishda xatolik", error);
      return null;
    }
  }

  async getCurrentInspections(): Promise<InspectionCount[]> {
    try {
      const response =
        await this.httpClient.get<InspectionCount[]>("/in_inspection_now");
      return response.data;
    } catch (error) {
      this.logger.error("Joriy tekshiruvlarni olishda xatolik", error);
      throw error;
    }
  }

  async getTotalInspectionCounts(): Promise<InspectionCount[]> {
    try {
      const response = await this.httpClient.get<InspectionCount[]>(
        "/inspection-counts/total",
      );
      return response.data;
    } catch (error) {
      this.logger.error("Umumiy tekshiruv sonlarini olishda xatolik", error);
      throw error;
    }
  }

  async getDepoInfo(depoId: number): Promise<DepoInfo | null> {
    try {
      const response = await this.httpClient.get<DepoInfo>("/depo-info", {
        params: { depo_id: depoId },
      });
      return response.data;
    } catch (error) {
      this.logger.error("Depo ma'lumotlarini olishda xatolik", error);
      return null;
    }
  }

  async getAllDeposInfo(): Promise<DepoInfo[]> {
    try {
      const response = await this.httpClient.get<DepoInfo[]>("/depo-info-all");
      return response.data;
    } catch (error) {
      this.logger.error("Barcha depolar ma'lumotlarini olishda xatolik", error);
      throw error;
    }
  }

  async getRepairStatsByYear(): Promise<RepairStatsByYear[]> {
    try {
      const response = await this.httpClient.get<RepairStatsByYear[]>(
        "/repairs/stats-by-year",
      );
      return response.data;
    } catch (error) {
      this.logger.error("Yillik ta'mir statistikasini olishda xatolik", error);
      throw error;
    }
  }

  translateState(state: string): string {
    const translations: Record<string, string> = {
      in_use: "Foydalanishda",
      in_inspection: "Tamirda",
      in_reserve: "Rezervda",
    };
    return translations[state] || state;
  }

  translateLocomotiveType(type: string): string {
    const translations: Record<string, string> = {
      electric_loco: "Elektrovoz",
      diesel_loco: "Teplovoz",
      electric_train: "Elektropoyezd",
      high_speed: "Yuqori tezlikli poyezd",
      carriage: "Vagon",
    };
    return translations[type] || type;
  }

  getStateFromUzbekQuery(query: string): string | null {
    const lowerQuery = query.toLowerCase();

    for (const [state, synonyms] of Object.entries(this.stateTranslations)) {
      if (synonyms.some((s) => lowerQuery.includes(s))) {
        return state;
      }
    }
    return null;
  }
}
