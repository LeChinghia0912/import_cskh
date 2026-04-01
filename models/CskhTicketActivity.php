<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Support\Carbon;

class CskhTicketActivity extends Model
{
    protected $connection = 'mysql4';

    protected $table = 'cskh_ticket_activities';

    // Bảng chỉ có created_at (không có updated_at)
    public $timestamps = false;

    protected $fillable = [
        'cskh_ticket_id',
        'user_id',
        'action',
        'type',
        'meta',
    ];

    protected $casts = [
        'created_at' => 'datetime',
        'meta' => 'array',
    ];

    protected static function booted(): void
    {
        // Vì timestamps=false, Eloquent sẽ không tự set created_at.
        // Đảm bảo created_at luôn có giá trị để timeline hiển thị đúng.
        static::creating(function (self $model) {
            if (empty($model->created_at)) {
                $model->created_at = Carbon::now();
            }
        });
    }

    public function ticket(): BelongsTo
    {
        return $this->belongsTo(CskhTicket::class, 'cskh_ticket_id');
    }

    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class, 'user_id');
    }
}

