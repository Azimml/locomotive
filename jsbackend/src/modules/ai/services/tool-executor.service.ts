import { Injectable, Logger } from "@nestjs/common";
import {
  LocomotiveApiService,
  Locomotive,
  Stats,
  LocomotiveTypeCount,
  ActiveRepair,
  LastRepair,
  LocomotiveModel,
  LocomotiveInfo,
  InspectionCount,
  DepoInfo,
  RepairStatsByYear,
} from "../../locomotive/locomotive-api.service";

export interface ToolResult {
  success: boolean;
  data: any;
  summary: string;
}

@Injectable()
export class ToolExecutorService {
  private readonly logger = new Logger(ToolExecutorService.name);

  constructor(private readonly locomotiveApi: LocomotiveApiService) {}

  async executeFunction(
    functionName: string,
    args: Record<string, any>,
  ): Promise<ToolResult> {
    this.logger.log(`Executing function: ${functionName}`);

    switch (functionName) {
      case "get_total_locomotives_count":
        return this.getTotalLocomotivesCount();

      case "get_locomotives_by_state":
        return this.getLocomotivesByState(args.state);

      case "get_stats":
        return this.getStats();

      case "get_locomotive_types":
        return this.getLocomotiveTypes();

      case "get_locomotive_models":
        return this.getLocomotiveModels();

      case "get_active_repairs":
        return this.getActiveRepairs();

      case "get_locomotive_last_repair":
        return this.getLocomotiveLastRepair(args.locomotive_name);

      case "get_all_last_repairs":
        return this.getAllLastRepairs();

      case "search_locomotive_by_name":
        return this.searchLocomotiveByName(args.name);

      case "get_locomotive_detailed_info":
        return this.getLocomotiveDetailedInfo(args.locomotive_name);

      case "get_current_inspections":
        return this.getCurrentInspections();

      case "get_total_inspection_counts":
        return this.getTotalInspectionCounts();

      case "get_depo_info":
        return this.getDepoInfo(args.depo_id);

      case "get_all_depos_info":
        return this.getAllDeposInfo();

      case "get_repair_stats_by_year":
        return this.getRepairStatsByYear();

      default:
        return {
          success: false,
          data: null,
          summary: `Noma'lum funksiya: ${functionName}`,
        };
    }
  }

  private async getTotalLocomotivesCount(): Promise<ToolResult> {
    const stats = await this.locomotiveApi.getStats();
    return {
      success: true,
      data: { total: stats.total_locomotives },
      summary: `Jami lokomotivlar soni: ${stats.total_locomotives} ta`,
    };
  }

  private async getLocomotivesByState(state: string): Promise<ToolResult> {
    const stats = await this.locomotiveApi.getStats();

    if (state === "all") {
      const stateDetails = stats.state_counts.map((sc) => ({
        state: this.locomotiveApi.translateState(sc.state),
        count: sc.count,
      }));

      return {
        success: true,
        data: {
          total: stats.total_locomotives,
          states: stateDetails,
        },
        summary: this.formatStatesSummary(stats),
      };
    }

    const stateCount = stats.state_counts.find((sc) => sc.state === state);
    const translatedState = this.locomotiveApi.translateState(state);

    if (stateCount) {
      return {
        success: true,
        data: {
          state: translatedState,
          count: stateCount.count,
          total: stats.total_locomotives,
          percentage: (
            (stateCount.count / stats.total_locomotives) *
            100
          ).toFixed(1),
        },
        summary: `${translatedState} holatidagi lokomotivlar: ${stateCount.count} ta (jami ${stats.total_locomotives} tadan ${((stateCount.count / stats.total_locomotives) * 100).toFixed(1)}%)`,
      };
    }

    return {
      success: false,
      data: null,
      summary: `"${state}" holati topilmadi`,
    };
  }

  private async getStats(): Promise<ToolResult> {
    const stats = await this.locomotiveApi.getStats();

    return {
      success: true,
      data: {
        total_locomotives: stats.total_locomotives,
        total_models: stats.total_models,
        state_counts: stats.state_counts.map((sc) => ({
          state: this.locomotiveApi.translateState(sc.state),
          state_code: sc.state,
          count: sc.count,
        })),
      },
      summary: this.formatFullStatsSummary(stats),
    };
  }

  private async getLocomotiveTypes(): Promise<ToolResult> {
    const types = await this.locomotiveApi.getLocomotiveTypes();
    const activeTypes = types.filter((t) => t.locomotive_count > 0);

    return {
      success: true,
      data: activeTypes.map((t) => ({
        type: this.locomotiveApi.translateLocomotiveType(t.locomotive_type),
        type_code: t.locomotive_type,
        count: t.locomotive_count,
      })),
      summary: this.formatTypesSummary(activeTypes),
    };
  }

  private async getLocomotiveModels(): Promise<ToolResult> {
    const models = await this.locomotiveApi.getLocomotiveModels();

    return {
      success: true,
      data: models.map((m) => ({
        name: m.name,
        type: this.locomotiveApi.translateLocomotiveType(m.locomotive_type),
        count: m.locomotive_count,
      })),
      summary: this.formatModelsSummary(models),
    };
  }

  private async getActiveRepairs(): Promise<ToolResult> {
    const repairs = await this.locomotiveApi.getActiveRepairs();

    return {
      success: true,
      data: {
        count: repairs.length,
        repairs: repairs.map((r) => ({
          locomotive_name: r.locomotive_name,
          repair_type: r.repair_type_name_uz || r.repair_type_name,
        })),
      },
      summary: this.formatActiveRepairsSummary(repairs),
    };
  }

  private async getLocomotiveLastRepair(
    locomotiveName: string,
  ): Promise<ToolResult> {
    const repair = await this.locomotiveApi.getLastRepair(
      undefined,
      locomotiveName,
    );

    if (!repair) {
      return {
        success: false,
        data: null,
        summary: `"${locomotiveName}" raqamli lokomotiv topilmadi yoki ta'mir ma'lumotlari mavjud emas`,
      };
    }

    const lastDate = repair.last_updated_at
      ? new Date(repair.last_updated_at).toLocaleDateString("uz-UZ", {
          year: "numeric",
          month: "long",
          day: "numeric",
          hour: "2-digit",
          minute: "2-digit",
        })
      : "Ma'lumot yo'q";

    return {
      success: true,
      data: {
        locomotive_name: repair.locomotive_name,
        repair_type: repair.repair_type_name_uz || repair.repair_type_name,
        last_updated: repair.last_updated_at,
      },
      summary: `${repair.locomotive_name} lokomotivining oxirgi ta'miri: ${repair.repair_type_name_uz || repair.repair_type_name} (${lastDate})`,
    };
  }

  private async getAllLastRepairs(): Promise<ToolResult> {
    const repairs = await this.locomotiveApi.getAllLastRepairs();

    return {
      success: true,
      data: {
        count: repairs.length,
        repairs: repairs.slice(0, 20).map((r) => ({
          locomotive_name: r.locomotive_name,
          repair_type: r.repair_type_name_uz || r.repair_type_name,
          last_updated: r.last_updated_at,
        })),
      },
      summary: `Jami ${repairs.length} ta lokomotivning oxirgi ta'mir ma'lumotlari mavjud`,
    };
  }

  private async searchLocomotiveByName(name: string): Promise<ToolResult> {
    const locomotives = await this.locomotiveApi.getLocomotives();
    const activeRepairs = await this.locomotiveApi.getActiveRepairs();
    const allLastRepairs = await this.locomotiveApi.getAllLastRepairs();

    // Log for debugging
    this.logger.debug(
      `Searching for locomotive: "${name}". Total available: ${locomotives.length}`,
    );

    // Normalize search term
    const searchTerm = name.trim().toLowerCase();

    // Try exact match first
    const exactMatch = locomotives.find(
      (l) => l.locomotive_full_name && l.locomotive_full_name.toLowerCase() === searchTerm,
    );

    if (exactMatch) {
      return this.getDetailedLocomotiveInfo(
        exactMatch,
        activeRepairs,
        allLastRepairs,
      );
    }

    // Try partial matches with better logic
    const partialMatches = locomotives.filter((l) => {
      if (!l.locomotive_full_name || !name) return false;

      const locName = l.locomotive_full_name.toLowerCase();
      const search = searchTerm;

      return (
        locName.includes(search) ||
        search.includes(locName) ||
        locName.endsWith(search) ||
        search.endsWith(locName) ||
        locName.split(" ").some((part) => part === search) ||
        locName.split("-").some((part) => part === search)
      );
    });

    if (partialMatches.length === 0) {
      // Debug: log available locomotive names for troubleshooting
      this.logger.debug(
        `No matches found for "${name}". Available locomotives: ${locomotives
          .slice(0, 5)
          .map((l) => l.locomotive_full_name)
          .join(", ")}...`,
      );

      return {
        success: false,
        data: { query: name, matches: [] },
        summary: `"${name}" raqamli lokomotiv topilmadi. Iltimos, lokomotiv raqamini to'liq va to'g'ri kiriting yoki boshqa raqamni sinab ko'ring.`,
      };
    }

    if (partialMatches.length === 1) {
      return this.getDetailedLocomotiveInfo(
        partialMatches[0],
        activeRepairs,
        allLastRepairs,
      );
    }

    const matchesWithDetails = partialMatches.slice(0, 10).map((l) => {
      const activeRepair = activeRepairs.find(
        (r) => r.locomotive_name === l.locomotive_full_name,
      );
      const lastRepair = allLastRepairs.find(
        (r) => r.locomotive_name === l.locomotive_full_name,
      );

      return {
        name: l.locomotive_full_name,
        state: this.locomotiveApi.translateState(l.state),
        state_code: l.state,
        current_repair: activeRepair
          ? activeRepair.repair_type_name_uz || activeRepair.repair_type_name
          : null,
        last_repair: lastRepair
          ? lastRepair.repair_type_name_uz || lastRepair.repair_type_name
          : null,
      };
    });

    return {
      success: true,
      data: {
        query: name,
        multiple_matches: true,
        total_matches: partialMatches.length,
        matches: matchesWithDetails,
      },
      summary: this.formatMultipleMatchesSummary(name, matchesWithDetails),
    };
  }

  private async getDetailedLocomotiveInfo(
    locomotive: Locomotive,
    activeRepairs: ActiveRepair[],
    allLastRepairs: LastRepair[],
  ): Promise<ToolResult> {
    const activeRepair = activeRepairs.find(
      (r) => r.locomotive_name === locomotive.locomotive_full_name,
    );
    const lastRepair = allLastRepairs.find(
      (r) => r.locomotive_name === locomotive.locomotive_full_name,
    );

    const repairHistory = allLastRepairs
      .filter((r) => r.locomotive_name === locomotive.locomotive_full_name)
      .sort(
        (a, b) =>
          new Date(b.last_updated_at || 0).getTime() -
          new Date(a.last_updated_at || 0).getTime(),
      );

    return {
      success: true,
      data: {
        id: locomotive.locomotive_id,
        name: locomotive.locomotive_full_name,
        state: this.locomotiveApi.translateState(locomotive.state),
        state_code: locomotive.state,
        is_in_repair: !!activeRepair,
        current_repair: activeRepair
          ? {
              type:
                activeRepair.repair_type_name_uz ||
                activeRepair.repair_type_name,
            }
          : null,
        last_repair: lastRepair
          ? {
              type:
                lastRepair.repair_type_name_uz || lastRepair.repair_type_name,
              date: lastRepair.last_updated_at,
            }
          : null,
      },
      summary: this.formatDetailedLocomotiveInfo(
        locomotive,
        activeRepair,
        lastRepair || null,
      ),
    };
  }

  private formatMultipleMatchesSummary(
    query: string,
    matches: Array<{
      name: string;
      state: string;
      current_repair: string | null;
      last_repair: string | null;
    }>,
  ): string {
    const lines = [
      `⚠️ "${query}" so'rovi bo'yicha ${matches.length} ta o'xshash lokomotiv topildi.`,
      ``,
      `Quyidagilardan birini tanlang:`,
      ``,
    ];

    matches.forEach((m, index) => {
      let status = m.state;
      if (m.current_repair) {
        status = `Tamirda (${m.current_repair})`;
      }
      lines.push(`${index + 1}. **${m.name}** — ${status}`);
    });

    lines.push(``);
    lines.push(
      `Aniq ma'lumot olish uchun to'liq raqamni yozing (masalan: "${matches[0]?.name}")`,
    );

    return lines.join("\n");
  }

  private formatDetailedLocomotiveInfo(
    locomotive: Locomotive,
    activeRepair: ActiveRepair | undefined,
    lastRepair: LastRepair | null,
  ): string {
    const lines = [`🚂 **Lokomotiv: ${locomotive.locomotive_full_name}**`, ``];

    lines.push(
      `📍 **Holati:** ${this.locomotiveApi.translateState(locomotive.state)}`,
    );

    if (activeRepair) {
      lines.push(``);
      lines.push(`🔧 **Hozirgi ta'mir:**`);
      lines.push(
        `   • Turi: ${activeRepair.repair_type_name_uz || activeRepair.repair_type_name}`,
      );
    }

    if (lastRepair) {
      const lastDate = lastRepair.last_updated_at
        ? new Date(lastRepair.last_updated_at).toLocaleDateString("uz-UZ", {
            year: "numeric",
            month: "long",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
          })
        : "Noma'lum";

      lines.push(``);
      lines.push(`📋 **Oxirgi ta'mir:**`);
      lines.push(
        `   • Turi: ${lastRepair.repair_type_name_uz || lastRepair.repair_type_name}`,
      );
      lines.push(`   • Sana: ${lastDate}`);
    }

    return lines.join("\n");
  }

  private formatStatesSummary(stats: Stats): string {
    const lines = [`Jami lokomotivlar: ${stats.total_locomotives} ta`];
    stats.state_counts.forEach((sc) => {
      const percentage = ((sc.count / stats.total_locomotives) * 100).toFixed(
        1,
      );
      lines.push(
        `• ${this.locomotiveApi.translateState(sc.state)}: ${sc.count} ta (${percentage}%)`,
      );
    });
    return lines.join("\n");
  }

  private formatFullStatsSummary(stats: Stats): string {
    const lines = [
      `📊 Umumiy statistika:`,
      `• Jami lokomotivlar: ${stats.total_locomotives} ta`,
      `• Jami modellar: ${stats.total_models} ta`,
      ``,
      `📈 Holat bo'yicha taqsimot:`,
    ];

    stats.state_counts.forEach((sc) => {
      const percentage = ((sc.count / stats.total_locomotives) * 100).toFixed(
        1,
      );
      lines.push(
        `• ${this.locomotiveApi.translateState(sc.state)}: ${sc.count} ta (${percentage}%)`,
      );
    });

    return lines.join("\n");
  }

  private formatTypesSummary(types: LocomotiveTypeCount[]): string {
    const total = types.reduce((sum, t) => sum + t.locomotive_count, 0);
    const lines = [`🚂 Lokomotiv turlari (jami ${total} ta):`];

    types.forEach((t) => {
      const percentage = ((t.locomotive_count / total) * 100).toFixed(1);
      lines.push(
        `• ${this.locomotiveApi.translateLocomotiveType(t.locomotive_type)}: ${t.locomotive_count} ta (${percentage}%)`,
      );
    });

    return lines.join("\n");
  }

  private formatModelsSummary(models: LocomotiveModel[]): string {
    const totalCount = models.reduce((sum, m) => sum + m.locomotive_count, 0);
    const lines = [
      `🚂 Lokomotiv modellari (jami ${models.length} ta model, ${totalCount} ta lokomotiv):`,
    ];

    const topModels = [...models]
      .sort((a, b) => b.locomotive_count - a.locomotive_count)
      .slice(0, 10);

    topModels.forEach((m) => {
      lines.push(
        `• ${m.name} (${this.locomotiveApi.translateLocomotiveType(m.locomotive_type)}): ${m.locomotive_count} ta`,
      );
    });

    if (models.length > 10) {
      lines.push(`... va yana ${models.length - 10} ta model`);
    }

    return lines.join("\n");
  }

  private formatActiveRepairsSummary(repairs: ActiveRepair[]): string {
    if (repairs.length === 0) {
      return `Hozirda tamirda bo'lgan lokomotiv yo'q`;
    }

    const lines = [`🔧 Hozirda tamirda: ${repairs.length} ta lokomotiv`];

    const repairTypes = new Map<string, number>();
    repairs.forEach((r) => {
      const type = r.repair_type_name_uz || r.repair_type_name;
      repairTypes.set(type, (repairTypes.get(type) || 0) + 1);
    });

    lines.push("");
    lines.push("Ta'mir turlari bo'yicha:");
    repairTypes.forEach((count, type) => {
      lines.push(`• ${type}: ${count} ta`);
    });

    return lines.join("\n");
  }

  private formatLocomotiveSearchResult(
    locomotive: Locomotive,
    lastRepair: LastRepair | null,
  ): string {
    const lines = [
      `🚂 Lokomotiv: ${locomotive.locomotive_full_name}`,
      `• Holati: ${this.locomotiveApi.translateState(locomotive.state)}`,
    ];

    if (lastRepair) {
      const lastDate = lastRepair.last_updated_at
        ? new Date(lastRepair.last_updated_at).toLocaleDateString("uz-UZ", {
            year: "numeric",
            month: "long",
            day: "numeric",
          })
        : "Ma'lumot yo'q";

      lines.push(
        `• Oxirgi ta'mir: ${lastRepair.repair_type_name_uz || lastRepair.repair_type_name} (${lastDate})`,
      );
    }

    return lines.join("\n");
  }

  private async getLocomotiveDetailedInfo(
    locomotiveName: string,
  ): Promise<ToolResult> {
    try {
      // Try to get detailed info from API
      const info = await this.locomotiveApi.getLocomotiveInfo(locomotiveName);

      if (info) {
        return {
          success: true,
          data: info,
          summary: this.formatLocomotiveDetailedInfo(info),
        };
      }

      // If direct API call didn't work, try searching for the locomotive
      this.logger.log(
        `Direct API call failed for "${locomotiveName}", attempting search...`,
      );
      return await this.searchLocomotiveByName(locomotiveName);
    } catch (error) {
      this.logger.error(
        `Error getting locomotive info for "${locomotiveName}":`,
        error,
      );
      // Fall back to search if there's an error
      return await this.searchLocomotiveByName(locomotiveName);
    }
  }

  private formatLocomotiveDetailedInfo(info: LocomotiveInfo): string {
    const lines = [
      `🚂 **${info.locomotive_full_name}**`,
      ``,
      `📍 **Asosiy ma'lumotlar:**`,
      `• Turi: ${this.locomotiveApi.translateLocomotiveType(info.locomotive_type)}`,
      `• Holati: ${this.locomotiveApi.translateState(info.state)}`,
      `• Joylashuvi: ${info.location_name}`,
      `• Depo: ${info.organization_name}`,
    ];

    // Yillik ta'mir statistikasi
    const years = Object.keys(info.repair_counts_by_year).sort(
      (a, b) => parseInt(b) - parseInt(a),
    );

    if (years.length > 0) {
      lines.push(``);
      lines.push(`📊 **Yillik ta'mir statistikasi:**`);

      for (const year of years) {
        const yearData = info.repair_counts_by_year[year];
        lines.push(`• ${year} yil: jami ${yearData.total} ta ta'mir`);
        const counts = Object.entries(yearData.counts)
          .map(([type, count]) => `  - ${type}: ${count} ta`)
          .join("\n");
        lines.push(counts);
      }
    }

    // Tekshiruv ma'lumotlari
    const inspectionEntries = Object.entries(info.inspection_details);
    if (inspectionEntries.length > 0) {
      lines.push(``);
      lines.push(`🔧 **Tekshiruv ma'lumotlari:**`);
      for (const [key, value] of inspectionEntries) {
        lines.push(`• ${key.trim()}: ${value}`);
      }
    }

    return lines.join("\n");
  }

  private async getCurrentInspections(): Promise<ToolResult> {
    const inspections = await this.locomotiveApi.getCurrentInspections();
    const activeInspections = inspections.filter((i) => i.locomotive_count > 0);

    const totalInInspection = inspections.reduce(
      (sum, i) => sum + i.locomotive_count,
      0,
    );

    return {
      success: true,
      data: {
        total: totalInInspection,
        inspections: activeInspections,
      },
      summary: this.formatCurrentInspections(
        activeInspections,
        totalInInspection,
      ),
    };
  }

  private formatCurrentInspections(
    inspections: InspectionCount[],
    total: number,
  ): string {
    const lines = [`🔧 **Hozirda tekshiruvda: ${total} ta lokomotiv**`, ``];

    if (inspections.length === 0) {
      lines.push(`Hozirda tekshiruvda lokomotiv yo'q.`);
      return lines.join("\n");
    }

    const sorted = [...inspections].sort(
      (a, b) => b.locomotive_count - a.locomotive_count,
    );

    for (const i of sorted) {
      lines.push(`• ${i.name_uz || i.name}: ${i.locomotive_count} ta`);
    }

    return lines.join("\n");
  }

  private async getTotalInspectionCounts(): Promise<ToolResult> {
    const inspections = await this.locomotiveApi.getTotalInspectionCounts();
    const activeInspections = inspections.filter((i) => i.locomotive_count > 0);

    const totalInspections = inspections.reduce(
      (sum, i) => sum + i.locomotive_count,
      0,
    );

    return {
      success: true,
      data: {
        total: totalInspections,
        inspections: activeInspections,
      },
      summary: this.formatTotalInspectionCounts(
        activeInspections,
        totalInspections,
      ),
    };
  }

  private formatTotalInspectionCounts(
    inspections: InspectionCount[],
    total: number,
  ): string {
    const lines = [
      `📊 **Umumiy tekshiruv statistikasi (jami ${total} ta):**`,
      ``,
    ];

    const sorted = [...inspections].sort(
      (a, b) => b.locomotive_count - a.locomotive_count,
    );

    for (const i of sorted) {
      const percentage = ((i.locomotive_count / total) * 100).toFixed(1);
      lines.push(
        `• ${i.name_uz || i.name}: ${i.locomotive_count} ta (${percentage}%)`,
      );
    }

    return lines.join("\n");
  }

  private async getDepoInfo(depoId: number): Promise<ToolResult> {
    const depo = await this.locomotiveApi.getDepoInfo(depoId);

    if (!depo) {
      return {
        success: false,
        data: null,
        summary: `${depoId} raqamli depo topilmadi. Mavjud depolar: 1-Chuqursoy, 2-Andijon, 3-Termez, 4-Qarshi, 5-Tinchlik, 6-Buxoro, 7-Urganch, 8-Qo'ng'irot.`,
      };
    }

    return {
      success: true,
      data: depo,
      summary: this.formatDepoInfo(depo),
    };
  }

  private formatDepoInfo(depo: DepoInfo): string {
    const lines = [
      `🏭 **${depo.depo_name}**`,
      ``,
      `📊 **Umumiy ma'lumot:**`,
      `• Jami lokomotivlar: ${depo.locomotive_count} ta`,
    ];

    // Lokomotiv turlari
    const typeEntries = Object.entries(depo.locomotive_type_counts);
    if (typeEntries.length > 0) {
      lines.push(``);
      lines.push(`🚂 **Lokomotiv turlari:**`);
      for (const [type, count] of typeEntries) {
        const percentage = ((count / depo.locomotive_count) * 100).toFixed(1);
        lines.push(
          `• ${this.locomotiveApi.translateLocomotiveType(type)}: ${count} ta (${percentage}%)`,
        );
      }
    }

    // Holatlar
    const stateEntries = Object.entries(depo.state_counts);
    if (stateEntries.length > 0) {
      lines.push(``);
      lines.push(`📍 **Holat bo'yicha:**`);
      for (const [state, count] of stateEntries) {
        const percentage = ((count / depo.locomotive_count) * 100).toFixed(1);
        lines.push(
          `• ${this.locomotiveApi.translateState(state)}: ${count} ta (${percentage}%)`,
        );
      }
    }

    return lines.join("\n");
  }

  private async getAllDeposInfo(): Promise<ToolResult> {
    const depos = await this.locomotiveApi.getAllDeposInfo();
    const totalLocomotives = depos.reduce(
      (sum, d) => sum + d.locomotive_count,
      0,
    );

    return {
      success: true,
      data: {
        total_depos: depos.length,
        total_locomotives: totalLocomotives,
        depos,
      },
      summary: this.formatAllDeposInfo(depos, totalLocomotives),
    };
  }

  private formatAllDeposInfo(
    depos: DepoInfo[],
    totalLocomotives: number,
  ): string {
    const lines = [
      `🏭 **Barcha depolar (jami ${depos.length} ta depo, ${totalLocomotives} ta lokomotiv)**`,
      ``,
    ];

    const sorted = [...depos].sort(
      (a, b) => b.locomotive_count - a.locomotive_count,
    );

    for (const depo of sorted) {
      const percentage = (
        (depo.locomotive_count / totalLocomotives) *
        100
      ).toFixed(1);
      const states = Object.entries(depo.state_counts)
        .map(
          ([state, count]) =>
            `${this.locomotiveApi.translateState(state)}: ${count}`,
        )
        .join(", ");

      lines.push(
        `📍 **${depo.depo_name}**: ${depo.locomotive_count} ta (${percentage}%)`,
      );
      lines.push(`   └ ${states}`);
    }

    return lines.join("\n");
  }

  private async getRepairStatsByYear(): Promise<ToolResult> {
    const stats = await this.locomotiveApi.getRepairStatsByYear();

    return {
      success: true,
      data: stats,
      summary: this.formatRepairStatsByYear(stats),
    };
  }

  private formatRepairStatsByYear(stats: RepairStatsByYear[]): string {
    const lines = [`📊 **Yillar bo'yicha ta'mir statistikasi:**`, ``];

    const sorted = [...stats].sort((a, b) => b.year - a.year);

    for (const yearStat of sorted) {
      lines.push(
        `📅 **${yearStat.year} yil** (jami ${yearStat.total_locomotives} ta lokomotiv)`,
      );

      const repairEntries = Object.entries(yearStat.repair_type_counts).sort(
        (a, b) => b[1] - a[1],
      );

      for (const [repairType, count] of repairEntries) {
        lines.push(`   • ${repairType}: ${count} ta`);
      }

      lines.push(``);
    }

    return lines.join("\n");
  }
}
