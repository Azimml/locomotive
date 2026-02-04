import { UsersService } from "@/modules/users";
import { Injectable, Logger } from "@nestjs/common";
import { ConfigService } from "@nestjs/config";
import { InjectRepository } from "@nestjs/typeorm";
import { Repository } from "typeorm";

@Injectable()
export class SeedService {
  private readonly logger = new Logger(SeedService.name);

  constructor(
    private readonly usersService: UsersService,
    private readonly configService: ConfigService,
  ) {}

  async seed() {
    await this.seedDefaultUser();
  }

  private async seedDefaultUser() {
    const defaultLogin = this.configService.get<string>("DEFAULT_ADMIN_LOGIN");
    const defaultPassword = this.configService.get<string>(
      "DEFAULT_ADMIN_PASSWORD",
    );

    if (!defaultLogin || !defaultPassword) {
      this.logger.warn("Default admin credentials not configured");
      return;
    }

    const exists = await this.usersService.exists(defaultLogin);

    if (!exists) {
      await this.usersService.create(
        defaultLogin,
        defaultPassword,
        "Administrator",
      );
      this.logger.log(`Default admin user created: ${defaultLogin}`);
    } else {
      this.logger.log("Default admin user already exists");
    }
  }
}
