"use strict";
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};
var LocomotiveApiService_1;
Object.defineProperty(exports, "__esModule", { value: true });
exports.LocomotiveApiService = void 0;
const common_1 = require("@nestjs/common");
const config_1 = require("@nestjs/config");
const axios_1 = require("axios");
let LocomotiveApiService = LocomotiveApiService_1 = class LocomotiveApiService {
    constructor(configService) {
        this.configService = configService;
        this.logger = new common_1.Logger(LocomotiveApiService_1.name);
        this.stateTranslations = {
            in_use: ["foydalanishda", "ekspluatatsiyada", "ishda", "liniyada"],
            in_inspection: ["tamirda", "remontda", "tekshiruvda"],
            in_reserve: ["rezervda", "bekor", "zahirada"],
        };
        this.httpClient = axios_1.default.create({
            baseURL: this.configService.get("LOCOMOTIVE_API_URL"),
            timeout: 30000,
            headers: {
                Accept: "application/json",
            },
        });
    }
    async getLocomotives() {
        try {
            const response = await this.httpClient.get("/locomotives");
            return response.data;
        }
        catch (error) {
            this.logger.error("Lokomotivlarni olishda xatolik", error);
            throw error;
        }
    }
    async getLocomotiveModels() {
        try {
            const response = await this.httpClient.get("/locomotive-models");
            return response.data;
        }
        catch (error) {
            this.logger.error("Lokomotiv modellarini olishda xatolik", error);
            throw error;
        }
    }
    async getStats() {
        try {
            const response = await this.httpClient.get("/stats");
            return response.data;
        }
        catch (error) {
            this.logger.error("Statistikani olishda xatolik", error);
            throw error;
        }
    }
    async getLocomotiveTypes() {
        try {
            const response = await this.httpClient.get("/locomotive-types");
            return response.data;
        }
        catch (error) {
            this.logger.error("Lokomotiv turlarini olishda xatolik", error);
            throw error;
        }
    }
    async getActiveRepairs() {
        try {
            const response = await this.httpClient.get("/repairs/active");
            return response.data;
        }
        catch (error) {
            this.logger.error("Faol ta'mirlarni olishda xatolik", error);
            throw error;
        }
    }
    async getAllLastRepairs() {
        try {
            const response = await this.httpClient.get("/repairs/last-all");
            return response.data;
        }
        catch (error) {
            this.logger.error("Oxirgi ta'mirlarni olishda xatolik", error);
            throw error;
        }
    }
    async getLastRepair(locomotiveId, locomotiveName) {
        try {
            const params = {};
            if (locomotiveId)
                params.locomotive_id = locomotiveId;
            if (locomotiveName)
                params.locomotive_name = locomotiveName;
            const response = await this.httpClient.get("/repairs/last", {
                params,
            });
            return response.data;
        }
        catch (error) {
            this.logger.error("Oxirgi ta'mirni olishda xatolik", error);
            return null;
        }
    }
    async getLocomotiveInfo(locomotiveName) {
        try {
            const response = await this.httpClient.get("/locomotive-info", { params: { locomotive_name: locomotiveName } });
            return response.data;
        }
        catch (error) {
            this.logger.error("Lokomotiv ma'lumotlarini olishda xatolik", error);
            return null;
        }
    }
    async getCurrentInspections() {
        try {
            const response = await this.httpClient.get("/in_inspection_now");
            return response.data;
        }
        catch (error) {
            this.logger.error("Joriy tekshiruvlarni olishda xatolik", error);
            throw error;
        }
    }
    async getTotalInspectionCounts() {
        try {
            const response = await this.httpClient.get("/inspection-counts/total");
            return response.data;
        }
        catch (error) {
            this.logger.error("Umumiy tekshiruv sonlarini olishda xatolik", error);
            throw error;
        }
    }
    async getDepoInfo(depoId) {
        try {
            const response = await this.httpClient.get("/depo-info", {
                params: { depo_id: depoId },
            });
            return response.data;
        }
        catch (error) {
            this.logger.error("Depo ma'lumotlarini olishda xatolik", error);
            return null;
        }
    }
    async getAllDeposInfo() {
        try {
            const response = await this.httpClient.get("/depo-info-all");
            return response.data;
        }
        catch (error) {
            this.logger.error("Barcha depolar ma'lumotlarini olishda xatolik", error);
            throw error;
        }
    }
    async getRepairStatsByYear() {
        try {
            const response = await this.httpClient.get("/repairs/stats-by-year");
            return response.data;
        }
        catch (error) {
            this.logger.error("Yillik ta'mir statistikasini olishda xatolik", error);
            throw error;
        }
    }
    translateState(state) {
        const translations = {
            in_use: "Foydalanishda",
            in_inspection: "Tamirda",
            in_reserve: "Rezervda",
        };
        return translations[state] || state;
    }
    translateLocomotiveType(type) {
        const translations = {
            electric_loco: "Elektrovoz",
            diesel_loco: "Teplovoz",
            electric_train: "Elektropoyezd",
            high_speed: "Yuqori tezlikli poyezd",
            carriage: "Vagon",
        };
        return translations[type] || type;
    }
    getStateFromUzbekQuery(query) {
        const lowerQuery = query.toLowerCase();
        for (const [state, synonyms] of Object.entries(this.stateTranslations)) {
            if (synonyms.some((s) => lowerQuery.includes(s))) {
                return state;
            }
        }
        return null;
    }
};
exports.LocomotiveApiService = LocomotiveApiService;
exports.LocomotiveApiService = LocomotiveApiService = LocomotiveApiService_1 = __decorate([
    (0, common_1.Injectable)(),
    __metadata("design:paramtypes", [config_1.ConfigService])
], LocomotiveApiService);
//# sourceMappingURL=locomotive-api.service.js.map