import { Component } from '@angular/core';
import {MatBadgeModule} from '@angular/material/badge'
import { MatIcon } from "@angular/material/icon";
import {MatButtonModule} from "@angular/material/button";

@Component({
  selector: 'app-header',
  imports: [MatBadgeModule, MatIcon, MatButtonModule],
  templateUrl: './header.component.html',
  styleUrl: './header.component.scss',
})
export class HeaderComponent {

}
