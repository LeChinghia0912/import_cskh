<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class CskhSolution extends Model
{
    protected $connection = 'mysql4';

    protected $table = 'cskh_solutions';

    public $timestamps = false;

    protected $fillable = [
        'ticket_id',
        'resolution_text',
        'latest_reason',
        'status_id',
        'created_at',
    ];

    protected $casts = [
        'created_at' => 'datetime',
    ];

    public function ticket(): BelongsTo
    {
        return $this->belongsTo(CskhTicket::class, 'ticket_id');
    }

    public function status(): BelongsTo
    {
        return $this->belongsTo(CskhStatus::class, 'status_id');
    }
}
