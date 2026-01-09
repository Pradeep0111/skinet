import { Component, inject } from '@angular/core';
import {MatBadgeModule} from '@angular/material/badge'
import { MatIcon } from "@angular/material/icon";
import {MatButtonModule} from "@angular/material/button";
import { RouterLink, RouterLinkActive } from '@angular/router';
import { BusyService } from '../../Core/services/busy.service';
import { MatProgressBar } from "@angular/material/progress-bar";
import { CartService } from '../../Core/services/cart.service';

@Component({
  selector: 'app-header',
  imports: [MatBadgeModule, MatIcon, MatButtonModule, RouterLink, RouterLinkActive, MatProgressBar],
  templateUrl: './header.component.html',
  styleUrl: './header.component.scss',
})
export class HeaderComponent {
  busyService = inject(BusyService);
  cartService = inject(CartService);
}
