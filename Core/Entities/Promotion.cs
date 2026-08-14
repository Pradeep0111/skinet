namespace Core.Entities;

public class Promotion
{
    public decimal SalePrice { get; set; }
    public string? Label { get; set; }
    public DateTime? StartsAt { get; set; }
    public DateTime? EndsAt { get; set; }
    public bool IsActive { get; set; }

    public bool IsCurrentlyActive()
    {
        if (!IsActive) return false;

        var now = DateTime.UtcNow;
        return (!StartsAt.HasValue || StartsAt <= now)
            && (!EndsAt.HasValue || EndsAt >= now);
    }
}