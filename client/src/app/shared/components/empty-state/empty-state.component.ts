import { Component, inject, input, output } from '@angular/core';
import { MatIcon } from "@angular/material/icon";
import { MatAnchor } from "@angular/material/button";
import { RouterLink } from "@angular/router";
import { BusyService } from '../../../Core/services/busy.service';

@Component({
  selector: 'app-empty-state',
  imports: [MatIcon, MatAnchor],
  templateUrl: './empty-state.component.html',
  styleUrl: './empty-state.component.scss',
})
export class EmptyStateComponent {
  busyService = inject(BusyService);
  message = input.required<string>();
  icon = input.required<string>();
  actionText = input.required<string>();
  action = output<void>();

  onAction(){
    this.action.emit();
  }
}
