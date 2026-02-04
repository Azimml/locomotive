import { Module, OnModuleInit } from "@nestjs/common";
import { ConfigModule, ConfigService } from "@nestjs/config";
import { TypeOrmModule } from "@nestjs/typeorm";

import { SeedService } from "./database/seeds/seed.service";
import { getDatabaseConfig } from "./config/database.config";
import { AuthModule } from "./modules/auth";
import { UsersModule } from "./modules/users";
import { ChatModule } from "./modules/chat";
import { AiModule } from "./modules/ai";
import { LocomotiveModule } from "./modules/locomotive";

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      envFilePath: ".env",
    }),
    TypeOrmModule.forRootAsync({
      imports: [ConfigModule],
      useFactory: getDatabaseConfig,
      inject: [ConfigService],
    }),
    AuthModule,
    UsersModule,
    ChatModule,
    AiModule,
    LocomotiveModule,
  ],
  providers: [SeedService],
})
export class AppModule implements OnModuleInit {
  constructor(private readonly seedService: SeedService) {}

  async onModuleInit() {
    await this.seedService.seed();
  }
}
