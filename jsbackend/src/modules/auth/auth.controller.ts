import { Controller, Post, Body, HttpCode, HttpStatus } from "@nestjs/common";
import { ApiTags, ApiOperation, ApiResponse } from "@nestjs/swagger";
import { AuthService } from "./auth.service";
import { LoginDto } from "./dto/login.dto";

@ApiTags("auth")
@Controller("api/auth")
export class AuthController {
  constructor(private readonly authService: AuthService) {}

  @Post("login")
  @HttpCode(HttpStatus.OK)
  @ApiOperation({ summary: "Foydalanuvchi kirishi" })
  @ApiResponse({ status: 200, description: "Muvaffaqiyatli kirish" })
  @ApiResponse({ status: 401, description: "Noto'g'ri login yoki parol" })
  async login(@Body() loginDto: LoginDto) {
    return this.authService.login(loginDto);
  }
}
