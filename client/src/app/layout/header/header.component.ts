import { Component, inject } from '@angular/core';
import {MatBadgeModule} from '@angular/material/badge'
import { MatIcon } from "@angular/material/icon";
import {MatButtonModule} from "@angular/material/button";
import { Router, RouterLink, RouterLinkActive } from '@angular/router';
import { BusyService } from '../../Core/services/busy.service';
import { MatProgressBar } from "@angular/material/progress-bar";
import { CartService } from '../../Core/services/cart.service';
import { AccountService } from '../../Core/services/account.service';
import { MatMenu, MatMenuItem, MatMenuTrigger } from '@angular/material/menu';
import { MatDivider } from "@angular/material/divider";
import { IsAdminDirective } from "../../shared/directives/is-admin.directives";

@Component({
  selector: 'app-header',
  imports: [MatBadgeModule, MatIcon, MatButtonModule, RouterLink, RouterLinkActive, MatProgressBar, MatMenuTrigger, MatMenu, MatMenuItem, MatDivider, IsAdminDirective],
  templateUrl: './header.component.html',
  styleUrl: './header.component.scss',
})
export class HeaderComponent {
  busyService = inject(BusyService);
  cartService = inject(CartService);
  accountService = inject(AccountService);
  private router = inject(Router);

  logout(){
    this.accountService.logout().subscribe({
      next: () => {
        this.accountService.currentUser.set(null);
        this.router.navigateByUrl('/');
      }
    })
  }
}
